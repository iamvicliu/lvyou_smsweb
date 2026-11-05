"""SMS / call history API and the board webhook endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import (
    CallRecord,
    CallRecording,
    Device,
    SessionLocal,
    SmsJob,
    SmsRecord,
    get_db,
)
from backend.messages import (
    KEY_BARK_URL,
    KEY_NOTIFY_SECRET,
    KEY_NOTIFY_WEBHOOK,
    KEY_WEBHOOK_TOKEN,
    get_setting,
    ingest_push,
    notify_sms,
    poll_device,
    send_bark,
    send_dingtalk,
    set_setting,
)
from backend.security import client_ip_from_request, is_device_ip_allowed
from backend.settings_store import device_credential

logger = logging.getLogger("board-manager")

router = APIRouter()


def _device_label(db: Session, device_id: Optional[int], dev_id: str) -> str:
    device = None
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
    if device is None and dev_id:
        device = db.query(Device).filter(Device.devId == dev_id).first()
    if device is None:
        return dev_id or "-"
    return device.alias or device.devId or device.ip


def _sim_number_map(db: Session, rows) -> Dict[int, tuple]:
    """Device id -> (SIM1 本机号, SIM2 本机号) for the page being returned.

    The history rows only carry ``sim1`` / ``sim2``; the human-readable number
    lives on the device, so one extra query per page is enough.
    """
    ids = {r.device_id for r in rows if r.device_id}
    if not ids:
        return {}
    return {
        d.id: ((d.sim1number or "").strip(), (d.sim2number or "").strip())
        for d in db.query(Device).filter(Device.id.in_(ids)).all()
    }


def _row_sim_number(sim_map: Dict[int, tuple], device_id: Optional[int], slot: str) -> str:
    pair = sim_map.get(device_id or 0)
    if not pair:
        return ""
    return pair[0] if str(slot or "").endswith("1") else pair[1]


def _recording_map(db: Session, rows) -> Dict[int, Dict[str, Any]]:
    """CallRecord.id -> the recording that belongs to that call.

    Uploads carry ``telStartTs`` from the board, which is the same value the
    call record is keyed on, so the exact match covers the normal case. The
    ±2 minute fallback keeps recordings attached when a board reports the
    push with a slightly different timestamp than the call-detail push.
    """
    starts = [r.start_ts for r in rows if r.start_ts]
    if not starts:
        return {}
    dev_ids = {r.dev_id for r in rows if r.dev_id}
    query = db.query(CallRecording).filter(
        CallRecording.start_ts >= min(starts) - 120,
        CallRecording.start_ts <= max(starts) + 120,
    )
    if dev_ids:
        query = query.filter(CallRecording.dev_id.in_(dev_ids))
    recs = query.order_by(CallRecording.id.desc()).all()
    if not recs:
        return {}

    def payload(rec: CallRecording) -> Dict[str, Any]:
        return {
            "id": rec.id,
            "duration": rec.duration,
            "size": rec.size,
            "status": rec.status,
            "note": rec.note,
        }

    exact: Dict[tuple, CallRecording] = {}
    leftovers = []
    for rec in recs:
        key = (rec.dev_id, rec.start_ts)
        if key in exact:
            leftovers.append(rec)
        else:
            exact[key] = rec

    out: Dict[int, Dict[str, Any]] = {}
    unmatched = []
    for row in rows:
        rec = exact.get((row.dev_id, row.start_ts))
        if rec is None:
            unmatched.append(row)
        else:
            out[row.id] = payload(rec)
    for row in unmatched:
        best = None
        for rec in leftovers or recs:
            if rec.dev_id != row.dev_id:
                continue
            delta = abs((rec.start_ts or 0) - (row.start_ts or 0))
            if delta <= 120 and (best is None or delta < best[0]):
                best = (delta, rec)
        if best is not None:
            out[row.id] = payload(best[1])
            if best[1] in leftovers:
                leftovers.remove(best[1])
    return out


@router.get("/api/messages/sms")
def api_sms_history(
    device_id: int = Query(0, ge=0),
    q: str = Query("", max_length=128),
    direction: str = Query("", max_length=16),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(SmsRecord)
    if device_id:
        query = query.filter(SmsRecord.device_id == device_id)
    if direction in ("sent", "received"):
        query = query.filter(SmsRecord.direction == direction)
    if q:
        like = f"%{q}%"
        query = query.filter(SmsRecord.phone.like(like) | SmsRecord.content.like(like))
    total = query.count()
    rows = (
        query.order_by(SmsRecord.sms_ts.desc(), SmsRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    sim_map = _sim_number_map(db, rows)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "items": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "dev_id": r.dev_id,
                "device_name": _device_label(db, r.device_id, r.dev_id),
                "sim_slot": r.sim_slot,
                "sim_number": _row_sim_number(sim_map, r.device_id, r.sim_slot),
                "phone": r.phone,
                "content": r.content,
                "direction": r.direction,
                "sms_ts": r.sms_ts,
                "sms_time": r.sms_time,
            }
            for r in rows
        ],
    }


@router.get("/api/messages/threads")
def api_sms_threads(
    device_id: int = Query(0, ge=0),
    q: str = Query("", max_length=128),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """One row per phone number: the conversation list view."""
    from sqlalchemy import func

    base = db.query(SmsRecord)
    if device_id:
        base = base.filter(SmsRecord.device_id == device_id)
    if q:
        like = f"%{q}%"
        base = base.filter(SmsRecord.phone.like(like) | SmsRecord.content.like(like))

    grouped = (
        base.with_entities(
            SmsRecord.phone.label("phone"),
            func.max(SmsRecord.sms_ts).label("last_ts"),
            func.count(SmsRecord.id).label("total"),
        )
        .group_by(SmsRecord.phone)
        .subquery()
    )
    total = db.query(func.count()).select_from(grouped).scalar() or 0
    rows = (
        db.query(grouped)
        .order_by(grouped.c.last_ts.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        phone = row.phone or ""
        last = (
            base.filter(SmsRecord.phone == phone)
            .order_by(SmsRecord.sms_ts.desc(), SmsRecord.id.desc())
            .first()
        )
        received = (
            base.filter(SmsRecord.phone == phone, SmsRecord.direction == "received").count()
        )
        items.append({
            "phone": phone,
            "total": int(row.total or 0),
            "received": int(received),
            "last_ts": int(row.last_ts or 0),
            "last_time": last.sms_time if last else "",
            "last_content": last.content if last else "",
            "last_direction": last.direction if last else "",
            "device_name": _device_label(db, last.device_id, last.dev_id) if last else "",
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "items": items,
    }


@router.get("/api/messages/thread")
def api_sms_thread(
    phone: str = Query(..., max_length=64),
    device_id: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Every message exchanged with one number, oldest first, as chat bubbles."""
    query = db.query(SmsRecord).filter(SmsRecord.phone == phone)
    if device_id:
        query = query.filter(SmsRecord.device_id == device_id)
    rows = query.order_by(SmsRecord.sms_ts.desc(), SmsRecord.id.desc()).limit(limit).all()
    rows.reverse()
    sim_map = _sim_number_map(db, rows)
    return {
        "phone": phone,
        "items": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": _device_label(db, r.device_id, r.dev_id),
                "sim_slot": r.sim_slot,
                "sim_number": _row_sim_number(sim_map, r.device_id, r.sim_slot),
                "content": r.content,
                "direction": r.direction,
                "sms_ts": r.sms_ts,
                "sms_time": r.sms_time,
            }
            for r in rows
        ],
    }


@router.get("/api/messages/unread")
def api_unread(db: Session = Depends(get_db)):
    from backend import unread as unread_mod

    return unread_mod.by_device(db)


class SeenReq(BaseModel):
    kind: str


@router.post("/api/messages/seen")
def api_seen(req: SeenReq, db: Session = Depends(get_db)):
    from backend import unread as unread_mod

    if req.kind not in ("sms", "calls"):
        raise HTTPException(status_code=400, detail="kind 只能是 sms 或 calls")
    return {"ok": True, "seen_at": unread_mod.mark_seen(db, req.kind)}


@router.get("/api/messages/calls")
def api_call_history(
    device_id: int = Query(0, ge=0),
    q: str = Query("", max_length=128),
    direction: str = Query("", max_length=16),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CallRecord)
    if device_id:
        query = query.filter(CallRecord.device_id == device_id)
    if direction in ("incoming", "outgoing"):
        query = query.filter(CallRecord.direction == direction)
    if q:
        query = query.filter(CallRecord.phone.like(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(CallRecord.start_ts.desc(), CallRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    sim_map = _sim_number_map(db, rows)
    rec_map = _recording_map(db, rows)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "items": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "dev_id": r.dev_id,
                "device_name": _device_label(db, r.device_id, r.dev_id),
                "sim_slot": r.sim_slot,
                "sim_number": _row_sim_number(sim_map, r.device_id, r.sim_slot),
                "phone": r.phone,
                "direction": r.direction,
                "action": r.action,
                "duration": r.duration,
                "start_ts": r.start_ts,
                "call_time": r.call_time,
                "recording": rec_map.get(r.id),
            }
            for r in rows
        ],
    }


@router.post("/api/messages/refresh/{device_id}")
def api_messages_refresh(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    stats = poll_device(db, device)
    return {"ok": True, **stats}


@router.get("/api/messages/notify")
def api_notify_get(db: Session = Depends(get_db)):
    bark_url = (get_setting(db, KEY_BARK_URL, "") or "").strip()
    return {
        "notify_configured": bool(get_setting(db, KEY_NOTIFY_WEBHOOK, "")),
        "notify_secret_configured": bool(get_setting(db, KEY_NOTIFY_SECRET, "")),
        "webhook_token_configured": bool(get_setting(db, KEY_WEBHOOK_TOKEN, "")),
        "bark_configured": bool(bark_url),
        "bark_host": _url_host(bark_url),
    }


@router.post("/api/messages/notify")
async def api_notify_set(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Save DingTalk webhook / secret and the board push token.

    Empty string clears a value; absent keys are left untouched.
    ``rotate_webhook_token`` generates a fresh push token and returns it once.
    """
    if "dingtalk_webhook" in payload:
        set_setting(db, KEY_NOTIFY_WEBHOOK, str(payload.get("dingtalk_webhook") or "").strip())
    if "dingtalk_secret" in payload:
        set_setting(db, KEY_NOTIFY_SECRET, str(payload.get("dingtalk_secret") or "").strip())
    if "webhook_token" in payload:
        set_setting(db, KEY_WEBHOOK_TOKEN, str(payload.get("webhook_token") or "").strip())
    if "bark_url" in payload:
        bark_url = str(payload.get("bark_url") or "").strip()
        if bark_url and not (bark_url.startswith("https://") or bark_url.startswith("http://")):
            raise HTTPException(status_code=400, detail="Bark 地址必须以 http:// 或 https:// 开头")
        set_setting(db, KEY_BARK_URL, bark_url)
    response: Dict[str, Any] = {"ok": True}
    if payload.get("rotate_webhook_token"):
        token = secrets.token_urlsafe(24)
        set_setting(db, KEY_WEBHOOK_TOKEN, token)
        response["webhook_token"] = token
    if payload.get("test"):
        response["test_ok"] = await asyncio.to_thread(send_dingtalk, "绿邮面板通知测试 ✅", db)
    if payload.get("test_bark"):
        response["test_bark_ok"] = await asyncio.to_thread(
            send_bark, "绿邮 · 面板通知测试", "Bark 推送链路已连通 ✅", db
        )
    return response


def _url_host(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlsplit
        return urlsplit(url).netloc
    except Exception:
        return ""


@router.get("/api/sms/jobs/{tid}")
def api_sms_job(tid: str, db: Session = Depends(get_db)):
    job = db.query(SmsJob).filter(SmsJob.tid == tid).first()
    if job is None:
        raise HTTPException(status_code=404, detail="发送任务不存在")
    return {
        "tid": job.tid,
        "status": job.status,
        "note": job.note,
        "delivery_id": job.delivery_id,
        "updated": job.updated,
    }


def _webhook_authorized(request: Request, db: Session, payload: Dict[str, Any]) -> bool:
    expected = (get_setting(db, KEY_WEBHOOK_TOKEN, "") or "").strip()
    if expected:
        provided = str(
            request.query_params.get("k")
            or request.headers.get("x-webhook-token", "")
            or payload.get("k")
            or ""
        ).strip()
        # Once a token is configured it is the only accepted credential: a
        # request from the LAN with a wrong or missing token must not be
        # ingested, otherwise any device on the network can forge history.
        return bool(provided) and secrets.compare_digest(provided, expected)
    ip = client_ip_from_request(request)
    if not is_device_ip_allowed(ip):
        return False
    # No token configured yet: only LAN sources may push (onboarding default).
    return True


@router.post("/webhook")
async def api_webhook(request: Request):
    """Receive pushes from the boards (SMS, call state, sent-SMS result)."""
    ct = request.headers.get("content-type", "")
    try:
        raw = (await request.body()).decode("utf-8", "replace").strip()
        # Some firmware builds post the 603 hangup report as JSON while
        # labelling it text/plain. Sniff the body before falling back to form
        # parsing, otherwise that event arrives with no `type` at all.
        data = None
        if raw.startswith("{") or raw.startswith("["):
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
        if data is None:
            from urllib.parse import unquote
            data = dict(parse_qsl(unquote(raw)))
    except Exception:
        return {"status": "bad_request"}
    if not isinstance(data, dict):
        return {"status": "bad_request"}
    if not data.get("type"):
        # Untyped pushes are the board's "local push" format. Keep the shape
        # for diagnosing new firmware, but at debug level: the body carries
        # the caller number and message text.
        logger.debug("webhook untyped ct=%s keys=%s body=%s",
                     ct or "-", ",".join(sorted(data)[:12]) or "-",
                     re.sub(r"\d{7,}", "***", raw[:120]).replace("\n", " "))

    db = SessionLocal()
    try:
        if not _webhook_authorized(request, db, data):
            raise HTTPException(status_code=403, detail="webhook source not allowed")
        # One line per push: the only way to tell "board never sent 603" from
        # "panel dropped it" when a call ends without a record update.
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_push, db, data, client_ip_from_request(request)
        )
        logger.info(
            "webhook type=%s dev=%s slot=%s took=%.0fms",
            data.get("type"), data.get("devId"), data.get("slot"),
            (time.monotonic() - started) * 1000,
        )
        return result
    finally:
        db.close()
