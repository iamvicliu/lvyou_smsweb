#!/usr/bin/env python3
"""面板 + 板子全套自检（手动按需执行，不做定时轮询）。

在面板容器内运行：

    docker exec lvyou-smsweb python /tmp/selfcheck.py

检查项：
  1. 面板 /api/health 与容器时区
  2. 每块板子：心跳、可达性、时钟偏差、短信/通话存储开关、
     推送消息号、推送地址、自定义模板
  3. 板端 querysms/querytel 与面板库逐槽对账，统计漏入库条数
  4. Bark 服务器可达性（外网断了只报 WARN，不算板子故障）

退出码：0 = 全部通过（可有 WARN），1 = 存在 FAIL。
"""

from __future__ import annotations

import json
import re
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/app")

from backend.db import CallRecord, Device, SessionLocal, SmsRecord  # noqa: E402
from backend.device_client import ensure_device_token  # noqa: E402
from backend.messages import (  # noqa: E402
    _ping_window_seconds,
    device_call,
    get_setting,
)

PANEL_PORT = 34567
REQUIRED_MSGS = ("501", "502", "601", "602", "603", "998")


class Report:
    def __init__(self) -> None:
        self.fails = 0
        self.warns = 0
        self.lines: list[str] = []

    def _add(self, level: str, scope: str, text: str) -> None:
        self.lines.append(f"  [{level}] {scope} {text}")

    def ok(self, scope: str, text: str) -> None:
        self._add("PASS", scope, text)

    def warn(self, scope: str, text: str) -> None:
        self.warns += 1
        self._add("WARN", scope, text)

    def fail(self, scope: str, text: str) -> None:
        self.fails += 1
        self._add("FAIL", scope, text)

    def info(self, scope: str, text: str) -> None:
        self._add("INFO", scope, text)


def _http_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PANEL_PORT}/api/health", timeout=5
        ) as resp:
            return resp.status == 200, str(resp.status)
    except Exception as exc:  # noqa: BLE001 - 自检要报告原始原因
        return False, str(exc)[:80]


def _bark_reachable(db) -> tuple[bool, str]:
    url = get_setting(db, "bark_url", "") or ""
    if not url:
        return True, "未配置 Bark"
    host = urllib.parse.urlparse(url).hostname or ""
    if not host:
        return False, "Bark 地址无法解析"
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return False, "域名解析失败（面板所在主机没有外网）"
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=6) as raw:
            with ctx.wrap_socket(raw, server_hostname=host):
                return True, "可达"
    except Exception:
        return False, "HTTPS 连接失败（面板所在主机没有外网）"


def _parse_val(res: dict):
    val = res.get("val")
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _storage_ok(val: str) -> bool:
    text = str(val or "").replace(" ", "").lower()
    return all(flag in text for flag in ("1s:on", "1t:on", "2s:on", "2t:on"))


def _digits(value) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))


def _check_device(db, device: Device, report: Report) -> None:
    now = int(time.time())
    head = f"设备{device.id} {device.alias or device.ip}"
    report.lines.append("")
    report.lines.append(f"{head}  {device.ip}")

    age = now - int(device.lastSeen or 0)
    window = _ping_window_seconds(db, device)
    if age <= window:
        report.ok("心跳", f"最近 {age}s（窗口 {window}s）")
    else:
        report.fail("心跳", f"{age}s 未上报，超过 {window}s 窗口")

    try:
        token = ensure_device_token(db, device)
    except Exception as exc:  # noqa: BLE001
        report.fail("凭据", f"取令牌失败 {str(exc)[:60]}")
        return

    started = time.monotonic()
    inf = device_call(device.ip, token, "askinf", {}, timeout=8)
    if inf.get("code") != 0:
        report.fail("可达", f"askinf 失败 {inf.get('note') or inf.get('code')}")
        return
    report.ok("可达", f"askinf {int((time.monotonic() - started) * 1000)}ms")

    skew = now - int(inf.get("msgTs") or 0)
    if abs(skew) <= 180:
        report.ok("时钟", f"偏差 {skew}s")
    elif abs(skew) <= 600:
        report.warn("时钟", f"偏差 {skew}s（>3 分钟，建议校准）")
    else:
        report.fail("时钟", f"偏差 {skew}s（会打乱记录排序）")

    storage = device_call(device.ip, token, "storesmstelen", {}, timeout=8)
    if storage.get("code") != 0:
        report.warn("存储", f"查询失败 {storage.get('note') or storage.get('code')}")
    elif _storage_ok(storage.get("val")):
        report.ok("存储", str(storage.get("val")))
    else:
        report.fail("存储", f"未全开 {storage.get('val')}（重启板子后生效）")

    codes = _parse_val(device_call(device.ip, token, "askallmsgcode", {}, timeout=8))
    enabled = {str(x) for x in (codes.get("en") or [])} if isinstance(codes, dict) else set()
    missing = [m for m in REQUIRED_MSGS if m not in enabled]
    if not enabled:
        report.warn("推送开关", "读不到消息号列表")
    elif missing:
        report.fail("推送开关", f"缺少 {','.join(missing)}")
    else:
        report.ok("推送开关", "998/501/502/601/602/603 已开")

    push = _parse_val(inf)
    push_url = str(push.get("url") or "") if isinstance(push, dict) else ""
    target = urllib.parse.urlparse(push_url)
    if not push_url:
        report.fail("推送地址", "未配置")
    elif target.port == PANEL_PORT:
        report.ok("推送地址", f"指向本面板 :{PANEL_PORT}")
    else:
        report.warn("推送地址", f"指向 {target.hostname or '?'}:{target.port or '-'}")

    ids = device_call(device.ip, token, "askcustmsg", {}, timeout=8).get("val")
    if isinstance(ids, str) and ids.strip().startswith("["):
        try:
            ids_list = json.loads(ids)
        except Exception:
            ids_list = []
        custom = [str(x) for x in ids_list if str(x) in ("501", "502", "603")]
        if custom:
            report.info("自定义模板", f"{','.join(custom)}（Bark 文本，面板已解析）")

    for slot in ("1", "2"):
        res = device_call(
            device.ip, token, "querysms", {"p1": "0", "p2": "30", "p4": slot}, timeout=15
        )
        if res.get("code") != 0:
            report.warn(f"短信对账卡{slot}", f"querysms 失败 {res.get('note') or res.get('code')}")
            continue
        rows = res.get("results") or []
        board = {
            (int(m.get("smsTs") or 0), _digits(m.get("phNum"))[-4:])
            for m in rows
            if m.get("smsTs")
        }
        have = {
            (int(s.sms_ts or 0), _digits(s.phone)[-4:])
            for s in db.query(SmsRecord)
            .filter(SmsRecord.device_id == device.id, SmsRecord.sim_slot == f"sim{slot}")
            .all()
        }
        missing_n = len(board - have)
        if missing_n == 0:
            report.ok(f"短信对账卡{slot}", f"板端 {len(board)} 条，面板全部已入库")
        else:
            report.fail(f"短信对账卡{slot}", f"板端 {len(board)} 条，面板缺 {missing_n} 条")

    res = device_call(device.ip, token, "querytel", {"p1": "1", "p2": "20"}, timeout=12)
    if res.get("code") == 0 and isinstance(res.get("results"), list):
        rows = res["results"]
        board = {int(r.get("telStartTs") or 0) for r in rows if r.get("telStartTs")}
        have = {
            int(c.start_ts or 0)
            for c in db.query(CallRecord).filter(CallRecord.device_id == device.id).all()
        }
        missing_n = len(board - have)
        if missing_n == 0:
            report.ok("通话对账", f"板端 {len(board)} 条，面板全部已入库")
        else:
            report.fail("通话对账", f"板端 {len(board)} 条，面板缺 {missing_n} 条")

    card1 = (device.sim1operator or "未读取").strip() or "未读取"
    card2 = (device.sim2operator or "未读取").strip() or "未读取"
    report.info("卡状态", f"卡1 {card1} / 卡2 {card2}")


def main() -> int:
    report = Report()
    db = SessionLocal()
    try:
        ok, detail = _http_health()
        report.lines.append("[面板]")
        if ok:
            report.ok("健康", f"/api/health {detail}")
        else:
            report.fail("健康", f"/api/health 异常 {detail}")

        report.ok("时区", time.strftime("%Y-%m-%d %H:%M:%S %Z"))

        bark_ok, bark_detail = _bark_reachable(db)
        if bark_ok:
            report.ok("Bark", bark_detail)
        else:
            report.warn("Bark", f"{bark_detail}（只影响通知，不影响入库）")

        devices = db.query(Device).order_by(Device.id).all()
        report.lines.append("")
        report.lines.append(f"[板子] 共 {len(devices)} 块")
        for device in devices:
            try:
                _check_device(db, device, report)
            except Exception as exc:  # noqa: BLE001 - 单板异常不中断整体自检
                report.fail(f"设备{device.id}", f"检查异常 {str(exc)[:80]}")
    finally:
        db.close()

    print("\n".join(report.lines))
    verdict = "PASS" if report.fails == 0 else "FAIL"
    print("")
    print(f"结论：{verdict}  失败 {report.fails} 项 / 警告 {report.warns} 项")
    return 0 if report.fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
