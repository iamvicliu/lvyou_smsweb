"""SIM 初始化失败（209）的自动守护。

固件报 209 表示这张卡从头到尾没能初始化成功，官方说明里它不会自己重试，
恢复手段只有"重新插拔"或 ``slotrst`` 重启卡槽。但 209 也会误报（注册慢、
Wi-Fi 抖动、刚重启还没注册完），直接重启会把一张正在用的卡打断，还会让
板子掉线一分钟，所以这里按三步收敛：

1. 收到 209 先进 30 秒观察期；期间同槽的 204（就绪）/205（弹出）立即取消。
2. 观察期满只发 **一次** ``stat`` 做二次确认。官方的说法是主动查询只允许
   "心跳超时验证 / 用户单次刷新 / 故障诊断"，单次诊断正好落在允许范围内，
   并且这条路径永远不会循环——每次要重启只查一次。
3. ``slotN_sta`` 还在 NS / POWOFF / 缺失才重启卡槽；PIN 锁定、受限服务、
   无卡属于人工问题，重启解决不了，直接转人工。

``note`` 语义（固件定义）：1=PIN/PUK 锁定，2=受限服务（多半欠费），
3=注册超时，99=未知。1/2 不重启；3 直接重启；99 与未定义值要再确认一次
（25 秒后第二次 ``stat`` 仍异常才动）。

同一设备 24 小时内最多自动重启一次（滚动窗口，按设备而不是按卡槽），
收到 204 或 stat 报 OK 时清零。观察中 / 已取消只写日志不推送，避免误报刷屏；
只有真重启、恢复、转人工才推 Bark + 钉钉。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger("board-manager")

OBSERVE_SECONDS = 30.0
RECHECK_SECONDS = 25.0
VERIFY_SECONDS = 180.0
RESTART_COOLDOWN = 24 * 3600

ENABLED_KEY = "simguard_enabled"
MUTED_KEY = "simguard_muted"
RESTART_KEY = "simguard_restart:{dev_id}"
PING_KEY = "ping_intvl:{dev_id}"
NOTIFY_KEY = "simguard_notify:{dev_id}:{slot}:{kind}"

# 同一问题反复出现时逐级拉长提醒间隔：首次立即，之后 30 分钟、2 小时、
# 6 小时，最后封顶 24 小时。卡恢复（204/OK）即清零，下次异常立刻提醒。
NOTIFY_BACKOFF = (0, 30 * 60, 2 * 3600, 6 * 3600, 24 * 3600)

NOTE_TEXT = {
    1: "PIN/PUK 锁定",
    2: "受限服务（可能欠费或注册被拒）",
    3: "注册超时",
    99: "未知错误",
}

# note 1/2 重启无用；3 是可恢复的注册问题；99/未知先多确认一次。
_MANUAL_NOTES = {1, 2}
_RESTART_NOTES = {3}

_STATE_OK = "ok"
_STATE_OBSERVING = "observing"
_STATE_RESTARTED = "restarted"
_STATE_MANUAL = "manual"
_STATE_MUTED = "muted"


@dataclass
class _Pending:
    dev_id: str
    ip: str
    slot: int
    note: int
    label: str
    due: float
    stage: str = "observe"  # observe -> (recheck)
    device_ts: int = 0


_pending: Dict[str, _Pending] = {}
# dev_id -> {"slot": 1, "state": "...", "detail": "...", "updated": ts}
_states: Dict[str, Dict[str, Any]] = {}


def _key(dev_id: str, slot: int) -> str:
    return f"{dev_id or '-'}:{int(slot)}"


def _setting(db, key: str, default: str = "") -> str:
    from backend.messages import get_setting

    return get_setting(db, key, default)


def _set_setting(db, key: str, value: str) -> None:
    from backend.messages import set_setting

    set_setting(db, key, value)


def enabled(db=None) -> bool:
    """Guard switch; default on. ``BMSIMGUARD=0`` forces it off at boot."""
    import os

    env = os.environ.get("BMSIMGUARD")
    if env is not None and env.strip() in ("0", "false", "False", "no"):
        return False
    if db is None:
        from backend.db import SessionLocal

        db = SessionLocal()
        try:
            return _setting(db, ENABLED_KEY, "1") not in ("0", "false", "off", "")
        finally:
            db.close()
    return _setting(db, ENABLED_KEY, "1") not in ("0", "false", "off", "")


def set_enabled(value: bool) -> None:
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        _set_setting(db, ENABLED_KEY, "1" if value else "0")
    finally:
        db.close()


def _muted_set(db) -> set:
    raw = (_setting(db, MUTED_KEY, "") or "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def muted_devices() -> set:
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        return _muted_set(db)
    finally:
        db.close()


def set_muted(dev_id: str, muted: bool) -> None:
    """Per-board silence: skip 209 decisions *and* their pushes for one board."""
    dev_id = (dev_id or "").strip()
    if not dev_id:
        return
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        ids = _muted_set(db)
        if muted:
            ids.add(dev_id)
            # A pending check would otherwise fire after the user muted it.
            for key, p in list(_pending.items()):
                if (p.dev_id or "") == dev_id:
                    _pending.pop(key, None)
            _record(dev_id, 0, _STATE_MUTED, "已静音：忽略 209，不推送也不自动重启")
        else:
            ids.discard(dev_id)
            st = _states.get(dev_id) or {}
            if st.get("state") == _STATE_MUTED:
                _record(dev_id, int(st.get("slot") or 0), "ok", "已取消静音")
        _set_setting(db, MUTED_KEY, ",".join(sorted(ids)))
    finally:
        db.close()


def _record(dev_id: str, slot: int, state: str, detail: str) -> None:
    _states[dev_id or "-"] = {
        "slot": int(slot),
        "state": state,
        "detail": detail,
        "updated": int(time.time()),
    }
    logger.info("simguard %s slot%s: %s (%s)", dev_id or "-", slot, state, detail)


def _notify_check(dev_id: str, slot: int, kind: str) -> tuple[bool, int]:
    """(allowed, previous_count) for this device/slot/kind."""
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        raw = _setting(db, NOTIFY_KEY.format(dev_id=dev_id, slot=int(slot), kind=kind), "")
        try:
            st = json.loads(raw) if raw else {}
        except ValueError:
            st = {}
        n = int(st.get("n") or 0)
        last = float(st.get("last") or 0)
        wait = NOTIFY_BACKOFF[min(n, len(NOTIFY_BACKOFF) - 1)]
        if last and (time.time() - last) < wait:
            logger.info("simguard 通知退避：%s 卡%s %s 第 %s 次，还需 %.0f 秒",
                        dev_id, slot, kind, n + 1, wait - (time.time() - last))
            return False, n
        return True, n
    finally:
        db.close()


def _notify_mark(dev_id: str, slot: int, kind: str, count: int) -> None:
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        _set_setting(db, NOTIFY_KEY.format(dev_id=dev_id, slot=int(slot), kind=kind),
                     json.dumps({"n": int(count), "last": int(time.time())}))
    except Exception:
        db.rollback()
    finally:
        db.close()


def _notify_reset(dev_id: str, slot: int) -> None:
    if not dev_id:
        return
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        for kind in ("manual", "restarted", "info"):
            _set_setting(db, NOTIFY_KEY.format(dev_id=dev_id, slot=int(slot), kind=kind), "")
    except Exception:
        db.rollback()
    finally:
        db.close()


def _push(title: str, body: str, *, dev_id: str = "", slot: int = 0,
          kind: str = "info") -> None:
    """Best-effort Bark + DingTalk; a push failure must not break the guard."""
    count = 0
    if dev_id and kind != "recovered":
        allowed, count = _notify_check(dev_id, slot, kind)
        if not allowed:
            return
        if count:
            body = f"（同一问题第 {count + 1} 次提醒）\n{body}"
    try:
        from backend.messages import _run_async, send_bark, send_dingtalk

        _run_async(send_dingtalk, f"{title}\n{body}")
        _run_async(send_bark, title, body)
    except Exception:
        logger.debug("simguard push failed", exc_info=True)
    if dev_id:
        if kind == "recovered":
            _notify_reset(dev_id, slot)
        else:
            _notify_mark(dev_id, slot, kind, count + 1)


# ── Event intake ─────────────────────────────────────────────────────────────

def note_209(dev_id: str, ip: str, slot: int, note: int, label: str = "",
             device_ts: int = 0) -> None:
    """A 209 arrived: start (or refresh) the 30 s observation window."""
    try:
        slot_i = int(slot)
    except (TypeError, ValueError):
        slot_i = 1
    if slot_i not in (1, 2):
        return
    if dev_id and dev_id in muted_devices():
        cur = _states.get(dev_id) or {}
        if cur.get("state") != _STATE_MUTED:
            _record(dev_id, slot_i, _STATE_MUTED, "已静音：忽略 209，不推送也不自动重启")
        return
    now = time.time()
    key = _key(dev_id, slot_i)
    cur = _pending.get(key)
    if cur is not None:
        # Keep the first deadline: a board spamming 209 must not push the
        # check out forever, but the newest note is the one we act on.
        cur.note = int(note or 0) if note else cur.note
        cur.ip = ip or cur.ip
        cur.label = label or cur.label
        logger.debug("simguard %s slot%s: 209 repeated, deadline kept", dev_id, slot_i)
        return
    _pending[key] = _Pending(
        dev_id=dev_id or "",
        ip=ip or "",
        slot=slot_i,
        note=int(note or 0),
        label=label or dev_id or ip or "",
        due=now + OBSERVE_SECONDS,
        device_ts=int(device_ts or 0),
    )
    _record(dev_id, slot_i, _STATE_OBSERVING, f"收到 209（{NOTE_TEXT.get(int(note or 0), '未知')}），观察 30 秒")


def note_recovered(dev_id: str, slot: int, label: str = "") -> None:
    """204 arrived: the slot is usable, so drop any pending check and cooldown."""
    slot_i = int(slot or 1)
    key = _key(dev_id, slot_i)
    prev = (_states.get(dev_id or "-") or {}).get("state")
    if _pending.pop(key, None) is not None:
        logger.info("simguard %s slot%s: 观察期内恢复，取消", dev_id, slot_i)
        if prev == _STATE_RESTARTED:
            _record(dev_id, slot_i, _STATE_OK, "重启后收到 204，已恢复")
            _push("SIM 自愈 · 已恢复",
                  f"{label or dev_id} 卡{slot_i}\n卡槽已重新注册，冷却计数清零",
                  dev_id=dev_id, slot=slot_i, kind="recovered")
        else:
            _record(dev_id, slot_i, _STATE_OK, "观察期内收到 204，已取消")
    elif prev == _STATE_RESTARTED:
        # The board may report 204 without us still holding a pending entry
        # (the verify check can lag behind the push); still worth telling the
        # operator the restart worked.
        _record(dev_id, slot_i, _STATE_OK, "重启后收到 204，已恢复")
        _push("SIM 自愈 · 已恢复",
              f"{label or dev_id} 卡{slot_i}\n卡槽已重新注册，冷却计数清零",
              dev_id=dev_id, slot=slot_i, kind="recovered")
    _clear_cooldown(dev_id)


def note_removed(dev_id: str, slot: int) -> None:
    """205 arrived: no card, nothing to restart."""
    slot_i = int(slot or 1)
    if _pending.pop(_key(dev_id, slot_i), None) is not None:
        logger.info("simguard %s slot%s: 卡已弹出，取消", dev_id, slot_i)
        _record(dev_id, slot_i, "removed", "卡已弹出，取消守护")


def _clear_cooldown(dev_id: str) -> None:
    if not dev_id:
        return
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        _set_setting(db, RESTART_KEY.format(dev_id=dev_id), "")
    except Exception:
        db.rollback()
    finally:
        db.close()


# ── Decision ─────────────────────────────────────────────────────────────────

def _lookup_device(db, dev_id: str, ip: str):
    from backend.db import Device

    device = None
    if dev_id:
        device = db.query(Device).filter(Device.devId == dev_id).first()
    if device is None and ip:
        device = db.query(Device).filter(Device.ip == ip).first()
    return device


def _cooldown_remaining(db, dev_id: str) -> int:
    raw = _setting(db, RESTART_KEY.format(dev_id=dev_id), "")
    try:
        last = int(float(raw or 0))
    except (TypeError, ValueError):
        last = 0
    if not last:
        return 0
    left = RESTART_COOLDOWN - (time.time() - last)
    return max(0, int(left))


def _slot_state(res: Dict[str, Any], slot: int) -> str:
    info = res.get("slotInfo")
    if not isinstance(info, dict):
        return ""
    return str(info.get(f"slot{slot}_sta") or "").strip().upper()


def _remember_ping_interval(db, dev_id: str, res: Dict[str, Any]) -> None:
    try:
        iv = int(res.get("pingIntvl") or 0)
    except (TypeError, ValueError):
        iv = 0
    if 5 <= iv <= 600 and dev_id:
        try:
            _set_setting(db, PING_KEY.format(dev_id=dev_id), str(iv))
        except Exception:
            db.rollback()


def _advance(p: _Pending) -> None:
    from backend.db import SessionLocal
    from backend.device_client import ensure_device_token
    from backend.messages import device_call

    db = SessionLocal()
    try:
        device = _lookup_device(db, p.dev_id, p.ip)
        if device is None:
            _record(p.dev_id, p.slot, _STATE_MANUAL, "设备不在列表中，跳过")
            _pending.pop(_key(p.dev_id, p.slot), None)
            return
        label = p.label or device.alias or device.devId or device.ip
        try:
            token = ensure_device_token(db, device)
        except Exception as exc:
            _pending.pop(_key(p.dev_id, p.slot), None)
            _record(p.dev_id, p.slot, _STATE_MANUAL, f"取板子令牌失败：{exc}")
            _push("SIM 自愈 · 需人工", f"{label} 卡{p.slot}\n209 后无法取到板子令牌，未重启",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        res = device_call(device.ip, token, "stat", timeout=10)
        if int(res.get("code") or 0) != 0:
            # Device unreachable / refused: restarting blind could power-cycle
            # a board that is merely busy. Hand it to the operator instead.
            _pending.pop(_key(p.dev_id, p.slot), None)
            note = str(res.get("note") or res.get("code") or "")
            _record(p.dev_id, p.slot, _STATE_MANUAL, f"stat 查询失败（{note}），未重启")
            _push("SIM 自愈 · 需人工", f"{label} 卡{p.slot}\n收到 209，但 stat 查询失败：{note}",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        _remember_ping_interval(db, p.dev_id or device.devId or "", res)
        sta = _slot_state(res, p.slot)
        dev_time = str(res.get("devTime") or "")

        if p.stage == "verify":
            # 180 s after slotrst: one last diagnostic read. Success clears the
            # cooldown; failure stops here instead of retrying in a loop, so a
            # card that simply cannot register does not get power-cycled every
            # few minutes.
            _pending.pop(_key(p.dev_id, p.slot), None)
            if sta == "OK":
                _record(p.dev_id, p.slot, _STATE_OK, "重启后 stat 确认已恢复")
                _push("SIM 自愈 · 已恢复",
                      f"{label} 卡{p.slot}\n重启后已重新注册（{dev_time}），冷却计数清零",
                      dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="recovered")
                _clear_cooldown(p.dev_id or device.devId or "")
            else:
                _record(p.dev_id, p.slot, _STATE_MANUAL,
                        f"重启后仍为 {sta or '未知'}，转人工")
                _push("SIM 自愈 · 需人工",
                      f"{label} 卡{p.slot}\n已自动重启一次，3 分钟后仍为 {sta or '未知'}\n"
                      f"建议换卡或查欠费，24 小时内不会再次自动重启",
                      dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        if sta == "OK":
            _pending.pop(_key(p.dev_id, p.slot), None)
            _record(p.dev_id, p.slot, _STATE_OK, "stat 确认卡槽已正常，无需重启")
            _clear_cooldown(p.dev_id or device.devId or "")
            prev = (_states.get(p.dev_id or "-") or {}).get("state")
            if prev == _STATE_RESTARTED:
                _push("SIM 自愈 · 已恢复", f"{label} 卡{p.slot}\n重启后已重新注册（{dev_time}）",
                      dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="recovered")
            return

        if sta in ("PIN", "LT"):
            _pending.pop(_key(p.dev_id, p.slot), None)
            reason = "PIN/PUK 锁定" if sta == "PIN" else "受限服务（欠费或注册被拒）"
            _record(p.dev_id, p.slot, _STATE_MANUAL, f"stat：{sta}（{reason}），不重启")
            _push("SIM 自愈 · 需人工", f"{label} 卡{p.slot}\n卡槽状态 {sta}：{reason}\n重启解决不了，请查卡",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        if sta == "NOSIM":
            _pending.pop(_key(p.dev_id, p.slot), None)
            _record(p.dev_id, p.slot, _STATE_MANUAL, "stat：NOSIM，卡没插好")
            _push("SIM 自愈 · 需人工", f"{label} 卡{p.slot}\nstat 报 NOSIM，请检查卡是否插好",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        # NS / POWOFF / 空：确实是初始化没起来。
        if p.note in _MANUAL_NOTES:
            _pending.pop(_key(p.dev_id, p.slot), None)
            reason = NOTE_TEXT[p.note]
            _record(p.dev_id, p.slot, _STATE_MANUAL, f"note={p.note}（{reason}），不自动重启")
            _push("SIM 自愈 · 需人工",
                  f"{label} 卡{p.slot}\n209 note={p.note}：{reason}\n卡槽 {sta or '未知'}，未自动重启",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        if p.note not in _RESTART_NOTES and p.stage != "recheck":
            # note 99 / 未定义：再等一轮 stat，避免把偶发注册慢当成故障。
            p.stage = "recheck"
            p.due = time.time() + RECHECK_SECONDS
            _record(p.dev_id, p.slot, _STATE_OBSERVING,
                    f"note={p.note} 可疑，{int(RECHECK_SECONDS)} 秒后二次确认")
            return

        left = _cooldown_remaining(db, p.dev_id or device.devId or "")
        if left:
            _pending.pop(_key(p.dev_id, p.slot), None)
            hours = left / 3600
            _record(p.dev_id, p.slot, _STATE_MANUAL,
                    f"24 小时内已自动重启过，还剩 {hours:.1f} 小时冷却")
            _push("SIM 自愈 · 需人工",
                  f"{label} 卡{p.slot}\n卡槽 {sta}，但 24 小时冷却中（剩 {hours:.1f} 小时），未重启",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
            return

        r = device_call(device.ip, token, "slotrst",
                        {"p1": str(p.slot), "p2": "5"}, timeout=12)
        if int(r.get("code") or 0) == 0:
            _set_setting(db, RESTART_KEY.format(dev_id=p.dev_id or device.devId or ""),
                         str(int(time.time())))
            _record(p.dev_id, p.slot, _STATE_RESTARTED,
                    f"卡槽 {sta or '未知'} 且 note={p.note}，已 slotrst")
            note_txt = NOTE_TEXT.get(p.note, f"未知（{p.note}）")
            _push("SIM 自愈 · 已重启卡槽",
                  f"{label} 卡{p.slot}\n原因：209 note={p.note}（{note_txt}）\n"
                  f"确认时卡槽状态 {sta or '未知'}，板子时间 {dev_time}\n已下发 slotrst，约 1 分钟后重新注册",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="restarted")
            # Keep the entry so the loop checks once more after the card has
            # had time to re-register; a restart nobody confirms is how these
            # things silently stay broken.
            p.stage = "verify"
            p.due = time.time() + VERIFY_SECONDS
            return
        else:
            note = str(r.get("note") or r.get("code") or "")
            _record(p.dev_id, p.slot, _STATE_MANUAL, f"slotrst 被拒绝：{note}")
            _push("SIM 自愈 · 需人工", f"{label} 卡{p.slot}\nslotrst 失败：{note}",
                  dev_id=p.dev_id or device.devId or "", slot=p.slot, kind="manual")
        _pending.pop(_key(p.dev_id, p.slot), None)
    finally:
        db.close()


def tick() -> None:
    """Run every due check. Called from a 5 s background loop."""
    now = time.time()
    for key, p in list(_pending.items()):
        if p.due > now:
            continue
        try:
            _advance(p)
        except Exception:
            logger.debug("simguard advance failed for %s", key, exc_info=True)
            _pending.pop(key, None)


# ── UI snapshot ──────────────────────────────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    from backend.db import Device, SessionLocal

    db = SessionLocal()
    try:
        on = enabled(db)
        muted = _muted_set(db)
        rows = db.query(Device).all()
        items = []
        for d in rows:
            key = d.devId or d.ip
            st = _states.get(key) or {}
            cool = _cooldown_remaining(db, key) if key else 0
            pend = [
                {
                    "slot": p.slot,
                    "note": p.note,
                    "stage": p.stage,
                    "remaining": max(0, int(p.due - time.time())),
                }
                for p in _pending.values()
                if (p.dev_id or "") == (d.devId or "") and p.ip == d.ip
            ]
            items.append({
                "device_id": d.id,
                "devId": d.devId or "",
                "name": d.alias or d.devId or d.ip,
                "muted": bool(d.devId) and d.devId in muted,
                "state": st.get("state") or "",
                "detail": st.get("detail") or "",
                "updated": st.get("updated") or 0,
                "cooldown": cool,
                "pending": pend,
            })
        return {"ok": True, "enabled": on, "items": items}
    finally:
        db.close()


async def simguard_loop() -> None:
    import asyncio

    await asyncio.sleep(40)
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            logger.debug("simguard loop error", exc_info=True)
        await asyncio.sleep(5)
