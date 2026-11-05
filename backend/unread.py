"""Unread counters for the dashboard cards.

The panel never marks individual records as read; it only remembers when the
operator last looked at the SMS page and the call page. Counting "new since
then" is enough for a badge and keeps the record tables untouched.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import CallRecord, Setting, SmsRecord

SEEN_SMS = "seen:sms"
SEEN_CALLS = "seen:calls"


def _seen(db: Session, key: str) -> int:
    row = db.query(Setting).filter(Setting.key == key).first()
    try:
        return int(row.value) if row is not None and row.value else 0
    except (TypeError, ValueError):
        return 0


def mark_seen(db: Session, kind: str, ts: int = 0) -> int:
    """Advance the read cursor for one record type; returns the new cursor."""
    key = SEEN_SMS if kind == "sms" else SEEN_CALLS
    now = int(ts or time.time())
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        db.add(Setting(key=key, value=str(now)))
    else:
        row.value = str(now)
    db.commit()
    return now


def by_device(db: Session) -> Dict[str, Any]:
    """Per-device unread counters plus the fleet totals.

    A "missed" call is an incoming call whose final action was a missed one.
    Ringing rows are excluded: they are still in progress, not missed.
    """
    sms_since = _seen(db, SEEN_SMS)
    calls_since = _seen(db, SEEN_CALLS)

    per_device: Dict[int, Dict[str, int]] = {}
    sms_rows = (
        db.query(SmsRecord.device_id, func.count(SmsRecord.id))
        .filter(SmsRecord.direction == "received", SmsRecord.sms_ts > sms_since)
        .group_by(SmsRecord.device_id)
        .all()
    )
    for device_id, count in sms_rows:
        if device_id:
            per_device.setdefault(int(device_id), {"sms": 0, "missed": 0})["sms"] = int(count)

    call_rows = (
        db.query(CallRecord.device_id, func.count(CallRecord.id))
        .filter(
            CallRecord.direction == "incoming",
            CallRecord.action == "missed",
            CallRecord.start_ts > calls_since,
        )
        .group_by(CallRecord.device_id)
        .all()
    )
    for device_id, count in call_rows:
        if device_id:
            per_device.setdefault(int(device_id), {"sms": 0, "missed": 0})["missed"] = int(count)

    return {
        "devices": per_device,
        "sms": sum(v["sms"] for v in per_device.values()),
        "missed": sum(v["missed"] for v in per_device.values()),
        "sms_seen_at": sms_since,
        "calls_seen_at": calls_since,
    }
