"""Board health and live-control routes.

The dashboard already receives passive 998 heartbeats, so these endpoints are
deliberately on demand: opening the device sheet performs one ``stat`` read,
while restart and SIM-slot actions are explicit operator commands.

Live call control uses the same ``/ctrl`` API as the board's own auto-answer
feature.  The browser never carries call audio; it only sends call-control
commands and follows the resulting 601/602/603 pushes.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.audit import audit
from backend.db import CallRecord, Device, get_db
from backend.device_client import ensure_device_token
from backend.messages import device_call
from backend.security import is_device_ip_allowed

logger = logging.getLogger("board-manager")
router = APIRouter()


def _device_or_404(db: Session, device_id: int) -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


def _device_label(device: Device) -> str:
    return (device.alias or "").strip() or (device.devId or "").strip() or device.ip


def _call(device: Device, token: str, cmd: str, params: Optional[Dict[str, Any]] = None,
          timeout: float = 12.0) -> Dict[str, Any]:
    if not is_device_ip_allowed(device.ip):
        raise HTTPException(status_code=400, detail="设备 IP 不在允许的内网范围内")
    return device_call(device.ip, token, cmd, params, timeout=timeout)


def _accepted(response: Dict[str, Any]) -> bool:
    """A vendor command is accepted when code=0, even if type=401 means async."""
    try:
        return int(response.get("code", -1)) == 0
    except (TypeError, ValueError):
        return False


def _command_result(device: Device, action: str, response: Dict[str, Any]) -> Dict[str, Any]:
    ok = _accepted(response)
    note = str(response.get("note") or response.get("msg") or "")
    if not ok and not note:
        note = "板子没有接受命令"
    audit(
        "board_control",
        detail=f"device={device.id} ip={device.ip} action={action} ok={ok}",
        result="ok" if ok else "failed",
    )
    return {
        "ok": ok,
        "action": action,
        "code": response.get("code"),
        "type": response.get("type"),
        "note": note,
        "response": response,
    }


def _first_int(source: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key not in source:
            continue
        try:
            return int(source.get(key))
        except (TypeError, ValueError):
            continue
    return -1


def _health_from_stat(device: Device, stat: Dict[str, Any]) -> Dict[str, Any]:
    wifi = stat.get("wifi") if isinstance(stat.get("wifi"), dict) else {}
    slots = stat.get("slotInfo") if isinstance(stat.get("slotInfo"), dict) else {}
    sim_net = stat.get("simNet") if isinstance(stat.get("simNet"), list) else []
    slot_net = stat.get("slotNet") if isinstance(stat.get("slotNet"), list) else []
    usr_plmn = stat.get("usrPLMN") if isinstance(stat.get("usrPLMN"), list) else []

    slot_rows: List[Dict[str, Any]] = []
    for slot in (1, 2):
        prefix = f"sim{slot}_"
        stored_number = (device.sim1number if slot == 1 else device.sim2number) or ""
        stored_operator = (device.sim1operator if slot == 1 else device.sim2operator) or ""
        # X31v160 drops msIsdn/scName from slotInfo, so fall back to what the
        # operator typed into the panel instead of showing an empty field.
        net_mode = str(slot_net[slot - 1]).lower() if len(slot_net) >= slot else ""
        if net_mode:
            net_enabled = net_mode == "on"
        elif len(sim_net) >= slot:
            net_enabled = bool(sim_net[slot - 1])
        else:
            net_enabled = None
        slot_rows.append({
            "slot": slot,
            "state": str(slots.get(f"slot{slot}_sta") or ""),
            "signal": _first_int(slots, f"{prefix}dbm"),
            "plmn": str(slots.get(f"{prefix}plmn") or ""),
            "operator": str(slots.get(f"{prefix}scName") or stored_operator),
            "number": str(slots.get(f"{prefix}msIsdn") or stored_number),
            "net_mode": net_mode,
            "net_enabled": net_enabled,
            "user_plmn": str(usr_plmn[slot - 1]) if len(usr_plmn) >= slot else "",
        })

    # Firmware has used schRstHour in the published API and older aliases in
    # some builds; accept any *RstHour key so the card survives an OTA rename.
    daily_hour = _first_int(stat, "rstHour", "schRstHour", "dailyRstHour", "dailyrst")
    if daily_hour < 0:
        for key, value in stat.items():
            if str(key).lower().endswith("rsthour"):
                try:
                    daily_hour = int(value)
                except (TypeError, ValueError):
                    continue
                break
    return {
        "device_id": device.id,
        "name": _device_label(device),
        "ip": device.ip,
        "dev_id": str(stat.get("devId") or device.devId or ""),
        "firmware": str(stat.get("hwVer") or device.firmware_version or ""),
        "net_channel": _first_int(stat, "netCh"),
        "daily_restart_hour": daily_hour,
        "daily_restart_enabled": 0 <= daily_hour <= 23,
        "ping_interval": _first_int(stat, "pingIntvl"),
        "ack_timeout": _first_int(stat, "ackMax"),
        "wifi": {
            "mode": str(wifi.get("mode") or ""),
            "ssid": str(wifi.get("ssid") or ""),
            "ip": str(wifi.get("ip") or ""),
            "signal": _first_int(wifi, "dbm"),
            "tx_dbm": _first_int(wifi, "txdbm"),
        },
        "slots": slot_rows,
        "device_time": str(stat.get("devTime") or ""),
        "timezone": _first_int(stat, "devTz"),
        "uptime": _first_int(stat, "uptime"),
        "memory": _first_int(stat, "mem"),
        "msg_ts": _first_int(stat, "msgTs"),
        # The raw object is useful for diagnostics, but the UI only reads the
        # normalised fields above.
        "raw": stat,
    }


@router.get("/api/devices/{device_id}/health")
def api_device_health(device_id: int, db: Session = Depends(get_db)):
    device = _device_or_404(db, device_id)
    try:
        token = ensure_device_token(db, device)
        response = _call(device, token, "stat", timeout=10)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("health stat failed device=%s: %s", device.id, exc)
        return {"ok": False, "device_id": device.id, "error": str(exc)[:200]}
    if not _accepted(response):
        return {
            "ok": False,
            "device_id": device.id,
            "error": str(response.get("note") or "板子没有返回状态")[:200],
        }
    health = _health_from_stat(device, response)
    health["ok"] = True
    return health


class RebootReq(BaseModel):
    delay: int = 5


@router.post("/api/devices/{device_id}/reboot")
def api_device_reboot(device_id: int, req: RebootReq, db: Session = Depends(get_db)):
    device = _device_or_404(db, device_id)
    delay = max(1, min(30, int(req.delay or 5)))
    token = ensure_device_token(db, device)
    return _command_result(
        device, f"restart:{delay}s",
        _call(device, token, "restart", {"p1": delay}, timeout=10),
    )


class DailyRestartReq(BaseModel):
    enabled: bool = True
    hour: int = 4

    @field_validator("hour")
    @classmethod
    def _valid_hour(cls, value):
        if not 0 <= int(value) <= 23:
            raise ValueError("小时需在 0-23 之间")
        return int(value)


@router.get("/api/devices/{device_id}/daily-restart")
def api_daily_restart_get(device_id: int, db: Session = Depends(get_db)):
    device = _device_or_404(db, device_id)
    token = ensure_device_token(db, device)
    response = _call(device, token, "dailyrst", timeout=10)
    if not _accepted(response):
        return _command_result(device, "dailyrst:query", response)
    # X31v160 answers with note="Scheduled restart: every 1 day(s) at 4:00."
    # and no ``val``; older builds put the hour in ``val``.
    hour = -1
    raw_val = str(response.get("val") or "").strip()
    if raw_val.isdigit():
        hour = int(raw_val)
    else:
        match = re.search(r"at\s+(\d{1,2}):(\d{2})", str(response.get("note") or ""))
        if match:
            hour = int(match.group(1))
    return {
        "ok": True,
        "enabled": 0 <= hour <= 23,
        "hour": hour if 0 <= hour <= 23 else 4,
        "note": str(response.get("note") or ""),
    }


@router.post("/api/devices/{device_id}/daily-restart")
def api_daily_restart_set(device_id: int, req: DailyRestartReq,
                          db: Session = Depends(get_db)):
    device = _device_or_404(db, device_id)
    token = ensure_device_token(db, device)
    # The board stores 0-23 for an active hour and 24-99 for disabled.
    value = int(req.hour) if req.enabled else 25
    result = _command_result(
        device, f"dailyrst:{value}",
        _call(device, token, "dailyrst", {"p1": value}, timeout=10),
    )
    result["enabled"] = bool(req.enabled)
    result["hour"] = int(req.hour)
    return result


class SlotControlReq(BaseModel):
    slot: int
    action: str
    enabled: Optional[bool] = None

    @field_validator("slot")
    @classmethod
    def _valid_slot(cls, value):
        if int(value) not in (1, 2):
            raise ValueError("卡槽只能是 1 或 2")
        return int(value)

    @field_validator("action")
    @classmethod
    def _valid_action(cls, value):
        if value not in {"restart", "power", "net"}:
            raise ValueError("卡槽动作只能是 restart / power / net")
        return value


@router.post("/api/devices/{device_id}/slot-control")
def api_slot_control(device_id: int, req: SlotControlReq,
                     db: Session = Depends(get_db)):
    device = _device_or_404(db, device_id)
    token = ensure_device_token(db, device)
    if req.action == "restart":
        cmd, params = "slotrst", {"p1": req.slot, "p2": 5}
        action = f"slotrst:{req.slot}"
    else:
        if req.enabled is None:
            raise HTTPException(status_code=400, detail="请指定开启或关闭")
        cmd = "slotpwr" if req.action == "power" else "slotnet"
        state = "on" if req.enabled else "off"
        params = {"p1": req.slot, "p2": state}
        action = f"{cmd}:{req.slot}:{state}"
    return _command_result(device, action, _call(device, token, cmd, params, timeout=12))


class PhoneControlReq(BaseModel):
    deviceId: int
    slot: int
    action: str
    text: str = ""
    keys: str = ""
    duration: Optional[int] = None
    upload: bool = True
    repeat: int = 1
    pause: int = 1
    after_action: int = 0
    record: bool = False

    @field_validator("slot")
    @classmethod
    def _valid_slot(cls, value):
        if int(value) not in (1, 2):
            raise ValueError("卡槽只能是 1 或 2")
        return int(value)

    @field_validator("action")
    @classmethod
    def _valid_action(cls, value):
        allowed = {
            "answer", "hangup", "tts", "stop_tts", "dtmf", "clear_keys",
            "start_record", "stop_record",
        }
        if value not in allowed:
            raise ValueError("不支持的通话动作")
        return value


def _clamp(value: Optional[int], default: int, low: int, high: int) -> int:
    try:
        number = int(default if value is None else value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


@router.post("/api/tel/control")
def api_tel_control(req: PhoneControlReq, db: Session = Depends(get_db)):
    device = _device_or_404(db, req.deviceId)
    token = ensure_device_token(db, device)

    if req.action == "answer":
        text = (req.text or "").strip()[:2000]
        # The board hangs up on its own after p2 seconds; the vendor default is
        # 175, which is the sane ceiling for a takeover call.
        params: Dict[str, Any] = {
            "p1": req.slot,
            "p2": _clamp(req.duration, 175, 1, 175),
        }
        if text:
            params.update({
                "p3": text,
                "p4": _clamp(req.repeat, 1, 0, 20),
                "p5": _clamp(req.pause, 1, 1, 60),
                "p6": 1 if int(req.after_action) == 1 else 0,
            })
        elif req.record:
            # ``duration`` is the recording length here; the call itself keeps
            # the full 175 s ceiling so a 30 s recording does not end the call.
            params.update({
                "p2": 175,
                "p7": 1,
                "p8": _clamp(req.duration, 30, 1, 60),
                "p10": 1 if req.upload else 0,
            })
        cmd, action = "telanswer", "answer"
    elif req.action == "hangup":
        cmd, params, action = "telhangup", {"p1": req.slot}, "hangup"
    elif req.action == "tts":
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="请输入要播放的语音内容")
        cmd, action = "telstarttts", "tts"
        params = {
            "p1": req.slot,
            "p2": text[:2000],
            "p3": _clamp(req.repeat, 1, 0, 20),
            "p4": _clamp(req.pause, 1, 1, 60),
            "p5": 1 if int(req.after_action) == 1 else 0,
        }
    elif req.action == "stop_tts":
        cmd, action = "telstoptts", "stop_tts"
        params = {"p1": req.slot, "p2": 1 if int(req.after_action) == 1 else 0}
    elif req.action == "dtmf":
        keys = "".join(ch for ch in (req.keys or "") if ch in "0123456789ABCDabcd*#pPmM")
        if not keys:
            raise HTTPException(status_code=400, detail="按键为空或格式不正确")
        cmd, params, action = "telkeypress", {"p1": req.slot, "p2": keys[:200]}, "dtmf"
    elif req.action == "clear_keys":
        cmd, params, action = "telkeyclear", {"p1": req.slot}, "clear_keys"
    elif req.action == "start_record":
        cmd, action = "telstartrecord", "start_record"
        params = {
            "p1": req.slot,
            "p2": _clamp(req.duration, 60, 1, 60),
            "p4": 1 if req.upload else 0,
        }
    else:
        cmd, action = "telstoprecord", "stop_record"
        params = {"p1": req.slot, "p2": 1 if req.upload else 0}

    result = _command_result(
        device, f"tel:{action}:slot{req.slot}",
        _call(device, token, cmd, params, timeout=15),
    )
    # Keep the exact board parameters out of the browser response; they can
    # contain a TTS transcript or a phone number.
    result.pop("response", None)
    return result


def _event_type(raw_json: str) -> int:
    try:
        raw = json.loads(raw_json or "{}")
        return int(raw.get("type") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 0


@router.get("/api/tel/live")
def api_tel_live(db: Session = Depends(get_db)):
    """Calls whose latest push is ring/answer, scoped to the last six minutes.

    Board calls are capped at 175 seconds, so a much wider window would only
    surface stale rows from builds that missed the final 603/623 push.
    """
    cutoff = int(time.time()) - 360
    rows = (
        db.query(CallRecord)
        .filter(CallRecord.start_ts >= cutoff)
        .order_by(CallRecord.start_ts.desc(), CallRecord.id.desc())
        .limit(100)
        .all()
    )
    # 601/602 are inbound ring/answer; 620/621/622 are the outbound dial path,
    # where the far end rings but there is nothing to pick up on the board.
    active_types = {601: "ringing", 602: "answered", 620: "dialing",
                    621: "dialing", 622: "answered"}
    seen = set()
    items = []
    for row in rows:
        key = (row.device_id, row.sim_slot)
        if key in seen:
            continue
        seen.add(key)
        event = _event_type(row.raw_json or "")
        state = active_types.get(event)
        if not state:
            continue
        device = db.query(Device).filter(Device.id == row.device_id).first()
        items.append({
            "id": row.id,
            "device_id": row.device_id,
            "device_name": _device_label(device) if device else (row.dev_id or "-"),
            "slot": int(str(row.sim_slot or "sim1").replace("sim", "") or 1),
            "phone": row.phone,
            "direction": row.direction,
            "state": state,
            "event_type": event,
            "start_ts": row.start_ts,
            "call_time": row.call_time,
            "elapsed": max(0, int(time.time()) - int(row.start_ts or 0)),
        })
    return {"items": items, "server_ts": int(time.time())}
