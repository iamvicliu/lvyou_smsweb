"""Panel-side answer for inbound calls, with a recording length we control.

The board's own "接听并录音" mode records a fixed 15 seconds. Its firmware
builds the internal ``telanswer`` call with ``p8`` left at the vendor default,
and the management page (``/mgr?a=boardParamsMgr``) only exposes ring count and
total call length -- there is no field for the recording length at all.

``telanswer`` itself accepts ``p8`` up to 60 s, so the panel answers the ring
itself while the board is still waiting for its own ring counter. The board's
auto answer stays configured as a fallback: if the panel is down, or loses the
push, the call is still answered -- only the recording falls back to 15 s.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger("board-manager")

ENABLED_KEY = "auto_record_enabled"
SECONDS_KEY = "auto_record_seconds"
UPLOAD_KEY = "auto_record_upload"

DEFAULT_SECONDS = 60
MAX_SECONDS = 60

# A ringing push can repeat while the line stays up. One claim per ring keeps
# the second copy from sending a redundant telanswer that lands mid-call.
_claimed: Dict[str, float] = {}
_lock = threading.Lock()


def _setting(db, key: str, default: str) -> str:
    from backend.messages import get_setting

    return get_setting(db, key, default) or default


def read_settings(db) -> Dict[str, object]:
    enabled = _setting(db, ENABLED_KEY, "1") == "1"
    try:
        seconds = int(_setting(db, SECONDS_KEY, str(DEFAULT_SECONDS)))
    except (TypeError, ValueError):
        seconds = DEFAULT_SECONDS
    seconds = max(1, min(MAX_SECONDS, seconds))
    upload = _setting(db, UPLOAD_KEY, "1") == "1"
    return {"enabled": enabled, "seconds": seconds, "upload": upload}


def write_settings(db, enabled: bool, seconds: int, upload: bool) -> Dict[str, object]:
    from backend.messages import set_setting

    value = max(1, min(MAX_SECONDS, int(seconds)))
    set_setting(db, ENABLED_KEY, "1" if enabled else "0")
    set_setting(db, SECONDS_KEY, str(value))
    set_setting(db, UPLOAD_KEY, "1" if upload else "0")
    db.commit()
    return read_settings(db)


def _claim(key: str, ttl: float = 120.0) -> bool:
    now = time.time()
    with _lock:
        for old, stamp in list(_claimed.items()):
            if now - stamp > ttl:
                _claimed.pop(old, None)
        if key in _claimed:
            return False
        _claimed[key] = now
        return True


def answer_ring(device_id: int, slot: int, started: int) -> Optional[Dict[str, object]]:
    """Answer one ringing call and start a panel-length recording.

    Runs on a worker thread: the board gives a push only a few seconds before
    it retries, and a Digest handshake plus the command can take longer.
    """
    from backend.db import Device, SessionLocal
    from backend.device_client import ensure_device_token
    from backend.messages import device_call

    if slot not in (1, 2):
        return None
    if not _claim(f"{device_id}:{slot}:{started}"):
        return None

    db = SessionLocal()
    try:
        cfg = read_settings(db)
        if not cfg["enabled"]:
            return None
        device = db.query(Device).filter(Device.id == device_id).first()
        if device is None:
            return None

        # Leave manual takeover alone: mode 0 means the operator wants the
        # panel's "接听" button to decide, and mode 3 rejects the call.
        from backend.boardparams import read_params

        try:
            mode = int(read_params(device).get(f"cimd{slot}") or -1)
        except Exception:
            mode = -1
        if mode in (0, 3):
            logger.info(
                "auto answer skipped %s slot%s: board mode %s", device.ip, slot, mode
            )
            return {"ok": False, "code": -1, "note": f"board mode {mode}"}

        token = ensure_device_token(db, device)
        params = {
            "p1": slot,
            # Keep the line past the recording window so a 60 s cap does not
            # also hang the call up at 60 s.
            "p2": 175,
            "p7": 1,
            "p8": cfg["seconds"],
            "p10": 1 if cfg["upload"] else 0,
        }
        resp = device_call(device.ip, token, "telanswer", params, timeout=10)
        code = int(resp.get("code", -1) or -1)
        note = str(resp.get("note") or "")
        if code == 0:
            logger.info(
                "auto answered %s slot%s with %ss recording",
                device.ip, slot, cfg["seconds"],
            )
        else:
            # 200 here means the board's own timer already answered, or the
            # caller hung up first. Both are normal races, not failures.
            logger.info("auto answer skipped %s slot%s: %s", device.ip, slot, note or code)
        return {"ok": code == 0, "code": code, "note": note}
    except Exception:
        logger.warning("auto answer failed for device %s slot%s", device_id, slot, exc_info=True)
        return None
    finally:
        db.close()
