"""板子 → 面板 这一段链路的健康度，以及最近一次读到的运行指标。

Everything here is derived from messages the board already pushes; nothing in
this module calls a board. The vendor's monitoring guide forbids scheduled
polling, so the ping stream is the only continuous signal we are allowed to
use:

* 998 carries `cnt`, an auto-increment counter that restarts at 1 after a
  reboot, and is emitted every `pingIntvl` seconds (default 110).
* A jump in `cnt` means pings were lost on the way (or the queue was
  congested); a reset means the board rebooted.
* The arrival gap gives the effective interval without asking the board.

The numbers live in the `settings` table as one JSON row per board so the list
endpoint can render them without touching the network.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from backend.db import Setting

LINK_KEY = "link:{}"
HEALTH_KEY = "health:{}"

DEFAULT_INTERVAL = 110.0
MIN_INTERVAL = 5.0
MAX_INTERVAL = 600.0
# Offline threshold straight from the vendor doc: 3 x interval + 15s.
STALE_SLACK = 15.0


def _get(db: Session, key: str) -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return "" if row is None or row.value is None else str(row.value)


def _put(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def _load(db: Session, key: str) -> Dict[str, Any]:
    raw = _get(db, key)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _day(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


def device_key(device: Any) -> str:
    """Stable per-board key; every writer and reader must use this one."""
    if device is None:
        return ""
    return str(
        getattr(device, "devId", "")
        or getattr(device, "ip", "")
        or getattr(device, "id", "")
        or ""
    )


def _int(value: Any, default: int = -1) -> int:
    """int() that keeps a real 0 (memory can legitimately read 0%)."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def note_ping(
    db: Session,
    dev: str,
    data: Dict[str, Any],
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Fold one 998 into the board's link record."""
    now = time.time() if now is None else now
    key = LINK_KEY.format(dev or "unknown")
    state = _load(db, key)

    try:
        cnt = int(data.get("cnt") or 0)
    except (TypeError, ValueError):
        cnt = 0
    try:
        dev_ts = int(data.get("msgTs") or 0)
    except (TypeError, ValueError):
        dev_ts = 0
    if dev_ts > 10_000_000_000:  # some firmwares send milliseconds
        dev_ts //= 1000

    last_at = float(state.get("at") or 0)
    last_cnt = int(state.get("cnt") or 0)
    interval = float(state.get("interval") or DEFAULT_INTERVAL)
    today = _day(now)
    if state.get("today") != today:
        state["today"] = today
        state["arrivals"] = 0

    if last_at:
        gap = now - last_at
        threshold = interval * 3 + STALE_SLACK
        # Only believe gaps inside the configured range; a long gap is itself
        # an outage and must not drag the learned interval upwards.
        if MIN_INTERVAL <= gap <= MAX_INTERVAL:
            interval = interval * 0.7 + gap * 0.3
        if gap > threshold:
            state["gaps"] = int(state.get("gaps") or 0) + 1
            state["last_gap"] = int(gap)

    if cnt:
        if last_cnt and cnt > last_cnt:
            # A small forward step is loss; a wrap back to 1 is a reboot.
            missed = cnt - last_cnt - 1
            if 0 < missed < 1000:
                state["missed"] = int(state.get("missed") or 0) + missed
        elif last_cnt and cnt <= last_cnt:
            state["reboots"] = int(state.get("reboots") or 0) + 1
            state["reboot_at"] = int(now)
        state["cnt"] = cnt

    state.update({
        "at": int(now),
        "dev_ts": dev_ts,
        "interval": round(interval, 1),
        "arrivals": int(state.get("arrivals") or 0) + 1,
        "seen_at": int(state.get("seen_at") or now),
    })
    state["missed"] = int(state.get("missed") or 0)
    state["reboots"] = int(state.get("reboots") or 0)
    state["gaps"] = int(state.get("gaps") or 0)
    state["reboot_at"] = int(state.get("reboot_at") or 0)
    state["last_gap"] = int(state.get("last_gap") or 0)

    _put(db, key, json.dumps(state, ensure_ascii=False, separators=(",", ":")))
    return state


def summary(state: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    at = int(state.get("at") or 0)
    interval = float(state.get("interval") or DEFAULT_INTERVAL)
    threshold = interval * 3 + STALE_SLACK
    if not at:
        status = "unknown"
        age = 0
    else:
        age = max(0, int(now - at))
        if age <= threshold:
            status = "ok"
        elif age <= threshold * 2:
            status = "late"
        else:
            status = "down"
    return {
        "status": status,
        "age": age,
        "interval": int(round(interval)),
        "threshold": int(round(threshold)),
        "last_at": at,
        "arrivals": int(state.get("arrivals") or 0),
        "missed": int(state.get("missed") or 0),
        "gaps": int(state.get("gaps") or 0),
        "last_gap": int(state.get("last_gap") or 0),
        "reboots": int(state.get("reboots") or 0),
        "reboot_at": int(state.get("reboot_at") or 0),
        "cnt": int(state.get("cnt") or 0),
    }


def for_device(db: Session, dev: str, now: Optional[float] = None) -> Dict[str, Any]:
    return summary(_load(db, LINK_KEY.format(dev or "unknown")), now)


def bulk(db: Session, devs: Iterable[str], now: Optional[float] = None) -> Dict[str, Dict[str, Any]]:
    now = time.time() if now is None else now
    return {dev: for_device(db, dev, now) for dev in devs}


def cache_health(db: Session, dev: str, health: Dict[str, Any], now: Optional[float] = None) -> None:
    """Remember the last `stat` reading so the card can show it without a call."""
    now = time.time() if now is None else now
    wifi = health.get("wifi") or {}
    keep = {
        "uptime": _int(health.get("uptime")),
        "memory": _int(health.get("memory")),
        "net_channel": _int(health.get("net_channel")),
        "wifi_ssid": str(wifi.get("ssid") or ""),
        "wifi_signal": _int(wifi.get("signal")),
        "ping_interval": _int(health.get("ping_interval")),
        "daily_restart_hour": _int(health.get("daily_restart_hour")),
        "daily_restart_enabled": bool(health.get("daily_restart_enabled")),
        "at": int(now),
    }
    _put(db, HEALTH_KEY.format(dev or "unknown"), json.dumps(keep, ensure_ascii=False))


def cached_health(db: Session, dev: str, now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    data = _load(db, HEALTH_KEY.format(dev or "unknown"))
    if not data:
        return {}
    at = int(data.get("at") or 0)
    data["age"] = max(0, int(now - at)) if at else 0
    return data
