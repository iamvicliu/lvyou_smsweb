"""Keep a board's clock close to the server's.

The X31 stores local wall time in its RTC and reads it back as UTC after a
reboot, so a board that just restarted reports timestamps 8 hours behind.
Call records are ordered by ``start_ts`` taken straight from those pushes, so
an unsynced board buries its own calls at the bottom of the list -- they look
missing even though they were stored.

The vendor exposes ``now`` for exactly this. A push that arrives with a large
skew triggers one resync, rate limited per device so a board with a dead RTC
cannot be hammered every heartbeat.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from backend.db import Setting
from backend.device_client import ensure_device_token

logger = logging.getLogger("board-manager")

CST = timezone(timedelta(hours=8))

#: Ignore drift under three minutes: NTP jitter and clock granularity are not
#: worth a control command, and the ordering of records is unaffected.
SKEW_LIMIT_SECONDS = 180
#: The X31 can reset its RTC more than once in an evening. Ten minutes keeps a
#: flapping board from being hammered while still recovering the next reboot.
RESYNC_COOLDOWN_SECONDS = 10 * 60


def _skew(msg_ts: Any) -> Optional[int]:
    try:
        ts = int(msg_ts or 0)
    except (TypeError, ValueError):
        return None
    if ts > 10_000_000_000:  # some pushes carry milliseconds
        ts //= 1000
    if ts < 1_000_000_000:
        return None
    return int(time.time()) - ts


def _send_now(ip: str, token: str, when: int) -> None:
    """Set board time to Beijing wall clock with tz +8 and NTP enabled."""
    local = datetime.fromtimestamp(when, CST).strftime("%Y%m%d%H%M%S")
    try:
        httpx.get(
            f"http://{ip}/ctrl",
            params={"token": token, "cmd": "now", "p1": local, "p2": 15, "p3": 8},
            timeout=8,
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        )
    except Exception:
        logger.debug("clock resync failed for %s", ip, exc_info=True)


def maybe_fix(db, device, msg_ts: Any) -> bool:
    """Resync ``device`` when a live push shows its clock has drifted.

    Returns True only when a correction was actually dispatched, so the
    caller can schedule a one-shot history catch-up for a push that may have
    been dropped while the board's clock was wrong.
    """
    if device is None:
        return False
    skew = _skew(msg_ts)
    if skew is None or abs(skew) <= SKEW_LIMIT_SECONDS:
        return False
    now = int(time.time())
    dev_key = device.devId or str(device.id)
    setting_key = f"clockfix:{dev_key}"
    try:
        last = int(_get(db, setting_key, "0") or 0)
    except (TypeError, ValueError):
        last = 0
    if now - last < RESYNC_COOLDOWN_SECONDS:
        return False
    try:
        _put(db, setting_key, str(now))
    except Exception:
        logger.debug("clock guard marker write failed", exc_info=True)
        return False
    try:
        token = ensure_device_token(db, device)
    except Exception:
        logger.debug("clock guard token failed", exc_info=True)
        return False
    logger.warning("board clock off by %ss, resyncing dev=%s", skew, dev_key)
    threading.Thread(
        target=_send_now, args=(device.ip, token, now), daemon=True
    ).start()
    return True
def _get(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row is not None else default


def _put(db, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


