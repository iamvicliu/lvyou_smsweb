"""Fleet overview: the numbers the dashboard header needs in one round trip."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend import pushhealth
from backend.db import CallRecord, Device, SmsRecord, get_db

router = APIRouter()

CST = timezone(timedelta(hours=8))

# Mirrors frontend/src/utils/format.js simTone(): a card cannot be used.
# "无卡" is deliberately absent: an empty slot is a normal state (one board may
# only carry one card), so counting it as abnormal made the KPI cry wolf.
SIM_BAD = ("拒绝", "卡异常", "异常", "受限", "未注册", "欠费", "停机", "故障", "pin", "puk")
SIM_WARN = ("启动", "搜索", "注册中", "初始化", "飞行")


def _sim_tone(*values: Any) -> str:
    text = " ".join(str(v or "") for v in values).lower()
    if not text.strip():
        return ""
    if any(k in text for k in SIM_BAD):
        return "bad"
    if any(k in text for k in SIM_WARN):
        return "warn"
    return ""


def _midnight_ts() -> int:
    now = datetime.now(CST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp())


@router.get("/api/overview")
def api_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    devices = db.query(Device).all()
    online = sum(1 for d in devices if (d.status or "") == "online")
    bad = warn = sims = 0
    for d in devices:
        for slot in (1, 2):
            op = getattr(d, f"sim{slot}operator", "") or ""
            num = getattr(d, f"sim{slot}number", "") or ""
            if not op and not num:
                continue
            sims += 1
            tone = _sim_tone(op, num)
            if tone == "bad":
                bad += 1
            elif tone == "warn":
                warn += 1

    since = _midnight_ts()
    sms_in = db.query(SmsRecord).filter(
        SmsRecord.event_ts >= since, SmsRecord.direction == "received").count()
    sms_out = db.query(SmsRecord).filter(
        SmsRecord.event_ts >= since, SmsRecord.direction == "sent").count()
    calls_today = db.query(CallRecord).filter(CallRecord.event_ts >= since).count()
    missed = db.query(CallRecord).filter(
        CallRecord.event_ts >= since, CallRecord.direction == "incoming",
        CallRecord.duration == 0).count()

    push = pushhealth.stats(24)
    return {
        "devices": {"total": len(devices), "online": online, "offline": len(devices) - online},
        "sims": {"total": sims, "bad": bad, "warn": warn},
        "today": {
            "sms_in": sms_in,
            "sms_out": sms_out,
            "calls": calls_today,
            "missed": missed,
        },
        "push": push,
    }


@router.get("/api/notify/health")
def api_notify_health(hours: int = 24) -> Dict[str, Any]:
    hours = max(1, min(int(hours or 24), 24 * 7))
    return pushhealth.stats(hours)


@router.post("/api/notify/retry")
def api_notify_retry() -> Dict[str, Any]:
    sent = pushhealth.retry_due()
    return {"ok": True, "sent": sent, **pushhealth.stats(24)}
