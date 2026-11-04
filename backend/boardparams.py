"""Read and write the board's "运行参数" page (auto answer / recording).

The vendor exposes slot behaviour only through the HTML management page, not
through ``/ctrl``: ``/mgr?a=getHtmlData_boardParams`` returns the raw keys
(``cimd1``, ``cirn1``, ``cims1`` for answer mode, ring count and max call
seconds) while ``/mgr?a=saveBoardParams`` accepts the form's display names
(``answer_method_1`` ...). Both are protected by HTTP Digest with the same
admin credential the panel already stores for each board.

``cimd``: 0 = do not answer, 1 = auto answer, 2 = auto answer and record,
3 = reject. Recording only happens with mode 2, which is why the recording
card writes this page instead of a /ctrl command.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict

import httpx

from backend.settings_store import device_credential

logger = logging.getLogger("board-manager")

FIELDS = [
    "devId_stra", "devName_stra", "daily_rst", "daily_rst_iv",
    "cirn1", "cims1", "cimd1", "cirn2", "cims2", "cimd2",
    "sqgl", "qcsq", "def_devId_stra", "def_devName_stra",
]

DEFAULTS = {
    # Never invent identity fields here. If the board omits one of these,
    # saving the form would overwrite the board's real identity with a blank
    # or template-looking value, so write_params() refuses instead.
    "devId_stra": "",
    "devName_stra": "",
    "daily_rst": "4",
    "daily_rst_iv": "1",
    "cirn1": "2", "cimd1": "0", "cims1": "175",
    "cirn2": "2", "cimd2": "0", "cims2": "175",
    "sqgl": "30", "qcsq": "0",
}

_IDENTITY_FIELDS = ("devId_stra", "devName_stra")

ANSWER_MODES = {0: "不接听", 1: "自动接听", 2: "接听并录音", 3: "自动挂断"}

_lock = threading.Lock()


def _client(device) -> httpx.Client:
    user, password = device_credential(device)
    return httpx.Client(
        auth=httpx.DigestAuth(user, password),
        timeout=15,
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        follow_redirects=True,
    )


def read_params(device) -> Dict[str, str]:
    """Return the current parameter map (strings, as the board sends them)."""
    with _client(device) as client:
        resp = client.post(
            f"http://{device.ip}/mgr?a=getHtmlData_boardParams",
            data={"keys": json.dumps({"keys": FIELDS})},
        )
        resp.raise_for_status()
        payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "板子拒绝读取运行参数")
    data = payload.get("data") or {}
    return {k: str(v) for k, v in data.items()}


def write_params(device, updates: Dict[str, Any]) -> Dict[str, str]:
    """Merge ``updates`` (raw keys such as ``cimd1``) and save the whole form.

    The page has no partial-save mode: leaving a field out resets it to its
    built-in default, so every save starts from a fresh read.
    """
    with _lock:
        current = read_params(device)
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in current.items() if v not in (None, "")})
        for key, value in updates.items():
            merged[key] = str(value)
        missing = [key for key in _IDENTITY_FIELDS if not merged.get(key)]
        if missing:
            raise RuntimeError(
                "板子运行参数缺少设备标识，已拒绝保存：" + ", ".join(missing)
            )

        form = {
            "devId_stra": merged.get("devId_stra", DEFAULTS["devId_stra"]),
            "devName_stra": merged.get("devName_stra", DEFAULTS["devName_stra"]),
            "daily_rst": merged.get("daily_rst", "4"),
            "daily_rst_iv": merged.get("daily_rst_iv", "1"),
            "sqgl": merged.get("sqgl", "30"),
            "qcsq": merged.get("qcsq", "0"),
        }
        for slot in (1, 2):
            form[f"ring_count_{slot}"] = merged.get(f"cirn{slot}", "2")
            form[f"max_call_duration_{slot}"] = merged.get(f"cims{slot}", "175")
            form[f"answer_method_{slot}"] = merged.get(f"cimd{slot}", "0")

        with _client(device) as client:
            resp = client.post(f"http://{device.ip}/mgr?a=saveBoardParams", data=form)
            resp.raise_for_status()

        back = read_params(device)
        for key, value in updates.items():
            if str(back.get(key, "")) != str(value):
                raise RuntimeError(
                    f"保存后复查不一致：{key} 期望 {value}，实际 {back.get(key, '')}"
                )
        return back
