"""Call recordings: board upload endpoint, playback API and board setup.

The board POSTs one AMR file per call to
``/api/recordings/upload/<recording token>`` with the call context in the
query string. That path is public (the board has no login) and guarded by its
own token, separate from the panel login and from the push webhook token.
Everything else here requires a normal panel session.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import CallRecording, Device, SessionLocal, Setting, get_db, nowts
from backend.recordings import (
    AMR_MAGIC,
    MAX_BYTES,
    ffmpeg_binary,
    amr_duration_seconds,
    parse_media_part,
    recordings_root,
    store_amr,
    transcode_mp3,
)
from backend.security import is_device_ip_allowed, panel_base_url_for

logger = logging.getLogger("board-manager")

router = APIRouter()

KEY_RECORDING_TOKEN = "recording_token"


def _setting(db: Session, key: str) -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return (row.value if row else "") or ""


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def recording_token(db: Session) -> str:
    return (_setting(db, KEY_RECORDING_TOKEN) or "").strip()


def ensure_recording_token(db: Session) -> tuple[str, bool]:
    token = recording_token(db)
    if token:
        return token, False
    token = secrets.token_urlsafe(18)
    _set_setting(db, KEY_RECORDING_TOKEN, token)
    return token, True


def upload_url_for(db: Session, device: Device) -> str:
    """Build the telRecUrl the board should store for this device.

    The panel host is addressed by the LAN IP that shares a subnet with the
    board, so the same template works from every board without DNS.
    """
    token, _ = ensure_recording_token(db)
    base = panel_base_url_for(device.ip)
    # Board-side template syntax: double braces are substituted per call.
    return (
        f"{base}/api/recordings/upload/{token}"
        "?devId={{devId}}&slot={{slot}}&phNum={{phNum}}"
        "&telStartTs={{telStartTs}}&telConnectedTs={{telConnectedTs}}"
        "&telEndTs={{telEndTs}}&mediaId={{telMediaId}}"
    )


def _mask(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}…{token[-4:]}"


def _int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


@router.post("/api/recordings/upload/{token}")
async def api_recording_upload(token: str, request: Request):
    """Receive one AMR file from a board.

    Always answers the vendor's JSON shape: the board decides between 695 and
    696 from ``errcode``, so an HTTP-level 401 would only look like a network
    failure in its log.
    """
    db = SessionLocal()
    try:
        expected = recording_token(db)
        if not expected or not secrets.compare_digest(token, expected):
            logger.warning("recording upload rejected: bad token from %s",
                           request.client.host if request.client else "-")
            return JSONResponse(
                {"errcode": 401, "errmsg": "invalid token", "type": "",
                 "media_id": "", "created_at": 0}
            )

        length = _int(request.headers.get("content-length"))
        if length and length > MAX_BYTES + 64 * 1024:
            return JSONResponse(
                {"errcode": 413, "errmsg": "file too large", "type": "",
                 "media_id": "", "created_at": 0}
            )

        body = await request.body()
        part = parse_media_part(body, request.headers.get("content-type", ""))
        if part is None:
            return JSONResponse(
                {"errcode": 400, "errmsg": "missing media part", "type": "",
                 "media_id": "", "created_at": 0}
            )
        filename, payload = part
        if not payload:
            return JSONResponse(
                {"errcode": 400, "errmsg": "empty file", "type": "",
                 "media_id": "", "created_at": 0}
            )
        if len(payload) > MAX_BYTES:
            return JSONResponse(
                {"errcode": 413, "errmsg": "file too large", "type": "",
                 "media_id": "", "created_at": 0}
            )
        if not payload.startswith(AMR_MAGIC):
            return JSONResponse(
                {"errcode": 400, "errmsg": "Invalid file type", "type": "",
                 "media_id": "", "created_at": 0}
            )

        q = request.query_params
        dev_id = (q.get("devId") or "").strip()
        slot_raw = (q.get("slot") or "").strip()
        # Push events use "sim1"/"sim2"; the upload URL only carries 1/2.
        slot = f"sim{slot_raw}" if slot_raw.isdigit() else slot_raw
        phone = (q.get("phNum") or "").strip()
        start_ts = _int(q.get("telStartTs"))
        connected_ts = _int(q.get("telConnectedTs"))
        end_ts = _int(q.get("telEndTs"))
        media_id = (q.get("mediaId") or filename or "").strip()[:150]
        source_ip = request.client.host if request.client else ""
        if source_ip and not is_device_ip_allowed(source_ip):
            logger.info("recording upload from non-LAN ip %s (token ok)", source_ip)

        path = await asyncio.to_thread(store_amr, dev_id, payload)
        await asyncio.to_thread(transcode_mp3, path)
        duration = amr_duration_seconds(path)

        device = None
        if dev_id:
            device = db.query(Device).filter(Device.devId == dev_id).first()
        if device is None and source_ip:
            device = db.query(Device).filter(Device.ip == source_ip).first()

        dedup = f"{dev_id or '-'}|{start_ts}|{media_id or path.stem}"[:120]
        row = db.query(CallRecording).filter(CallRecording.dedup == dedup).first()
        if row is None:
            row = CallRecording(dedup=dedup, created=str(nowts()))
            db.add(row)
        row.device_id = device.id if device else row.device_id
        row.dev_id = dev_id or (device.devId if device else "") or ""
        row.slot = slot or row.slot or ""
        row.phone = phone or row.phone or ""
        row.start_ts = start_ts or row.start_ts or 0
        row.connected_ts = connected_ts or row.connected_ts or 0
        row.end_ts = end_ts or row.end_ts or 0
        row.media_id = media_id
        row.filename = filename[:150]
        row.size = len(payload)
        row.duration = duration or max(0, (end_ts or 0) - (connected_ts or start_ts or 0))
        row.stored_name = str(path.relative_to(recordings_root()))
        row.status = "stored"
        row.note = ""
        row.source_ip = source_ip
        db.commit()

        logger.info(
            "recording stored dev=%s slot=%s size=%d duration=%ds file=%s",
            row.dev_id, row.slot, row.size, row.duration, row.stored_name,
        )
        return {
            "errcode": 0,
            "errmsg": "success",
            "type": "amr",
            "media_id": media_id or path.stem,
            "created_at": int(time.time()),
        }
    except Exception:
        logger.exception("recording upload failed")
        return JSONResponse(
            {"errcode": 500, "errmsg": "server error", "type": "",
             "media_id": "", "created_at": 0}
        )
    finally:
        db.close()


def _recording_or_404(db: Session, rid: int) -> CallRecording:
    row = db.query(CallRecording).filter(CallRecording.id == rid).first()
    if row is None:
        raise HTTPException(status_code=404, detail="录音不存在")
    return row


def _file_for(row: CallRecording) -> tuple[Path, str]:
    """Return (path, media type), preferring the browser-friendly MP3."""
    base = recordings_root() / (row.stored_name or "")
    mp3 = base.with_suffix(".mp3")
    if mp3.exists() and mp3.stat().st_size > 0:
        return mp3, "audio/mpeg"
    if base.exists():
        # Lazy conversion: uploads made before ffmpeg was mounted, or a
        # conversion that failed once, get another chance on first play.
        if base.suffix == ".amr":
            made = transcode_mp3(base)
            if made:
                return made, "audio/mpeg"
        return base, "audio/amr"
    raise HTTPException(status_code=404, detail="录音文件已丢失")


@router.get("/api/recordings")
def api_recordings(
    device_id: int = Query(0, ge=0),
    q: str = Query("", max_length=128),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Recording list; the call history embeds the same rows per call."""
    query = db.query(CallRecording)
    if device_id:
        query = query.filter(CallRecording.device_id == device_id)
    if q:
        query = query.filter(CallRecording.phone.like(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(CallRecording.start_ts.desc(), CallRecording.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    devices = {
        d.id: (d.alias or d.devId or d.ip)
        for d in db.query(Device).all()
    }
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "items": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": devices.get(r.device_id or 0, r.dev_id or "-"),
                "dev_id": r.dev_id,
                "slot": r.slot,
                "phone": r.phone,
                "start_ts": r.start_ts,
                "duration": r.duration,
                "size": r.size,
                "status": r.status,
                "note": r.note,
                "created": r.created,
            }
            for r in rows
        ],
    }


@router.delete("/api/recordings/{rid}")
def api_recording_delete(rid: int, db: Session = Depends(get_db)):
    row = _recording_or_404(db, rid)
    base = recordings_root() / (row.stored_name or "")
    for path in (base, base.with_suffix(".mp3")):
        try:
            if row.stored_name and path.exists():
                path.unlink()
        except OSError:
            logger.warning("could not delete %s", path, exc_info=True)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/api/recordings/{rid}/audio")
def api_recording_audio(rid: int, db: Session = Depends(get_db)):
    row = _recording_or_404(db, rid)
    path, media_type = _file_for(row)
    return FileResponse(path, media_type=media_type)


@router.get("/api/recordings/{rid}/download")
def api_recording_download(rid: int, db: Session = Depends(get_db)):
    row = _recording_or_404(db, rid)
    path, media_type = _file_for(row)
    stamp = datetime.fromtimestamp(row.start_ts or time.time()).strftime("%Y%m%d_%H%M%S")
    safe_phone = "".join(ch for ch in (row.phone or "") if ch.isdigit() or ch == "+") or "unknown"
    return FileResponse(
        path, media_type=media_type,
        filename=f"{safe_phone}_{stamp}{path.suffix}",
    )


@router.get("/api/recordings/config")
def api_recording_config(reveal: int = Query(0), db: Session = Depends(get_db)):
    token = recording_token(db)
    rows = db.query(CallRecording).all()
    first = db.query(Device).order_by(Device.id).first()
    url = ""
    if token and first is not None:
        try:
            url = upload_url_for(db, first)
        except Exception:
            url = ""
    return {
        "token_configured": bool(token),
        "token_hint": _mask(token) if token else "",
        "upload_url": url if (reveal and url) else "",
        "count": len(rows),
        "bytes": sum(r.size or 0 for r in rows),
        "ffmpeg": bool(ffmpeg_binary()),
    }


@router.post("/api/recordings/token")
def api_recording_rotate(db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(18)
    _set_setting(db, KEY_RECORDING_TOKEN, token)
    return {"ok": True, "token": token}


@router.post("/api/recordings/setup")
def api_recording_setup(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Point the selected boards at this panel's upload endpoint.

    Also (re)enables 695/696 so the panel learns whether an upload worked.
    """
    from backend.routes.devices import PUSH_MSG_CODES
    from backend.device_client import ensure_device_token
    from backend.http_client import get_sync_client

    ids: List[int] = [int(x) for x in (payload.get("device_ids") or [])]
    if not ids:
        raise HTTPException(status_code=400, detail="device_ids required")

    _, created = ensure_recording_token(db)
    client = get_sync_client()
    items = []
    for device in db.query(Device).filter(Device.id.in_(ids)).all():
        item: Dict[str, Any] = {"device_id": device.id, "devId": device.devId or "",
                                "ip": device.ip, "ok": False}
        try:
            url = upload_url_for(db, device)
            dtok = ensure_device_token(db, device)

            def ctrl(**params: Any):
                resp = client.get(f"http://{device.ip}/ctrl",
                                  params={"token": dtok, **params},
                                  timeout=12)
                try:
                    return resp.json()
                except Exception:
                    return {}

            res = ctrl(cmd="setamrurl", p1=url)
            if int(res.get("code") or 0) != 0:
                raise RuntimeError(f"写入录音地址失败：{res.get('note') or res.get('code')}")
            res = ctrl(cmd="setallmsgcode", p1=PUSH_MSG_CODES, p2="on", p3="replace")
            if int(res.get("code") or 0) != 0:
                raise RuntimeError(f"开启消息号失败：{res.get('note') or res.get('code')}")
            back = ctrl(cmd="askamrurl")
            val = str(back.get("val") or "")
            if "/api/recordings/upload/" not in val:
                raise RuntimeError("复查失败：录音地址未生效")
            item.update(ok=True, url=val)
        except Exception as exc:
            logger.warning("recording setup failed for %s: %s", device.ip, exc)
            item["error"] = str(exc)[:200]
        items.append(item)
    return {"ok": all(i["ok"] for i in items) and bool(items),
            "token_created": created, "items": items}


class AnswerReq(BaseModel):
    device_ids: List[int]
    slots: List[int] = [1, 2]
    # 0 不接听 / 1 自动接听 / 2 接听并录音 / 3 自动挂断
    mode: int = 2
    ring: int = 1
    max_seconds: int = 15


class AnswerModeReq(BaseModel):
    slot: int
    mode: int


# Remembered per board+slot so "hand it back to the board" is one click. The
# value is the auto-answer mode the operator had before switching to manual.
ANSWER_PREV_KEY = "answer_prev:{device_id}:{slot}"


def _answer_slot_state(device, slot: int) -> Dict[str, Any]:
    from backend.boardparams import ANSWER_MODES, read_params

    params = read_params(device)
    mode = _int(params.get(f"cimd{slot}"))
    return {
        "mode": mode,
        "mode_label": ANSWER_MODES.get(mode, str(mode)),
        "ring": _int(params.get(f"cirn{slot}")),
        "max_seconds": _int(params.get(f"cims{slot}")),
    }


@router.get("/api/devices/{device_id}/answer-mode")
def api_answer_mode_get(device_id: int, db: Session = Depends(get_db)):
    """Current auto-answer mode per slot, plus the mode we paused for takeover."""
    from backend.messages import get_setting

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        slots = {str(slot): _answer_slot_state(device, slot) for slot in (1, 2)}
    except Exception as exc:
        logger.warning("answer-mode read failed for %s: %s", device.ip, exc)
        raise HTTPException(status_code=502, detail=f"读取接听设置失败：{exc}") from exc
    for slot in (1, 2):
        prev = get_setting(db, ANSWER_PREV_KEY.format(device_id=device.id, slot=slot), "")
        slots[str(slot)]["paused_mode"] = _int(prev) if prev else None
    return {"ok": True, "device_id": device.id, "slots": slots}


@router.post("/api/devices/{device_id}/answer-mode")
def api_answer_mode_set(device_id: int, req: AnswerModeReq, db: Session = Depends(get_db)):
    """Change only the answer mode of one slot.

    Auto-answer and live takeover fight over the same call: whichever touches it
    first wins. This endpoint is the arbitration switch — dropping a slot to
    mode 0 leaves ringing calls to the panel, and remembers the previous mode so
    the board can be handed the line back without re-entering the settings page.
    Ring count and call length stay untouched.
    """
    from backend.boardparams import write_params
    from backend.messages import get_setting, set_setting

    if req.slot not in (1, 2):
        raise HTTPException(status_code=400, detail="卡槽只能是 1 或 2")
    if req.mode not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="接听模式只能是 0/1/2/3")

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    key = ANSWER_PREV_KEY.format(device_id=device.id, slot=req.slot)
    try:
        before = _answer_slot_state(device, req.slot)
        back = write_params(device, {f"cimd{req.slot}": req.mode})
    except Exception as exc:
        logger.warning("answer-mode write failed for %s: %s", device.ip, exc)
        raise HTTPException(status_code=502, detail=f"板子没有接受修改：{exc}") from exc

    previous = before["mode"]
    if req.mode == 0 and previous != 0:
        set_setting(db, key, str(previous))
    elif req.mode != 0:
        set_setting(db, key, "")

    applied = _int(back.get(f"cimd{req.slot}"))
    paused = get_setting(db, key, "")
    return {
        "ok": applied == req.mode,
        "device_id": device.id,
        "slot": req.slot,
        "mode": applied,
        "previous": previous,
        "paused_mode": _int(paused) if paused else None,
        "ring": _int(back.get(f"cirn{req.slot}")),
        "max_seconds": _int(back.get(f"cims{req.slot}")),
    }


@router.get("/api/recordings/answer")
def api_recording_answer_config(db: Session = Depends(get_db)):
    """Current auto-answer settings, read straight from each board."""
    from backend.boardparams import ANSWER_MODES, read_params

    items = []
    for device in db.query(Device).order_by(Device.id).all():
        item: Dict[str, Any] = {
            "device_id": device.id,
            "devId": device.devId or "",
            "name": device.alias or device.devId or device.ip,
            "ip": device.ip,
            "slots": {},
        }
        try:
            params = read_params(device)
            for slot in (1, 2):
                mode = _int(params.get(f"cimd{slot}"))
                item["slots"][str(slot)] = {
                    "mode": mode,
                    "mode_label": ANSWER_MODES.get(mode, str(mode)),
                    "ring": _int(params.get(f"cirn{slot}")),
                    "max_seconds": _int(params.get(f"cims{slot}")),
                }
            item["ok"] = True
        except Exception as exc:
            item["ok"] = False
            item["error"] = str(exc)[:200]
        items.append(item)
    return {"items": items}


@router.post("/api/recordings/answer")
def api_recording_answer_set(payload: AnswerReq, db: Session = Depends(get_db)):
    """Write answer mode / ring count / max seconds for the selected boards.

    Mode 2 is what makes the board save the call audio at all; the file is
    then uploaded to this panel through the recording URL.
    """
    from backend.boardparams import write_params

    if payload.mode not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="接听模式只能是 0/1/2/3")
    if not 0 <= payload.ring <= 30:
        raise HTTPException(status_code=400, detail="响铃次数需在 0-30 之间")
    if not 1 <= payload.max_seconds <= 999:
        raise HTTPException(status_code=400, detail="最大通话时长需在 1-999 秒之间")
    slots = sorted({s for s in payload.slots if s in (1, 2)}) or [1, 2]

    items = []
    for device in db.query(Device).filter(Device.id.in_(payload.device_ids)).all():
        item: Dict[str, Any] = {
            "device_id": device.id,
            "name": device.alias or device.devId or device.ip,
            "ip": device.ip,
            "ok": False,
        }
        try:
            updates = {}
            for slot in slots:
                updates[f"cimd{slot}"] = payload.mode
                updates[f"cirn{slot}"] = payload.ring
                updates[f"cims{slot}"] = payload.max_seconds
            back = write_params(device, updates)
            item["ok"] = True
            item["applied"] = {
                str(slot): {
                    "mode": _int(back.get(f"cimd{slot}")),
                    "ring": _int(back.get(f"cirn{slot}")),
                    "max_seconds": _int(back.get(f"cims{slot}")),
                }
                for slot in slots
            }
        except Exception as exc:
            logger.warning("answer config failed for %s: %s", device.ip, exc)
            item["error"] = str(exc)[:200]
        items.append(item)
    return {"ok": bool(items) and all(i["ok"] for i in items), "items": items}
