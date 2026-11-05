"""Push delivery health and retry queue.

``send_bark`` used to report failure only to the log: if the Bark key was
revoked or the phone was offline, an SMS could arrive without any alert and
nothing on the panel showed it. This module keeps a small ring of attempts,
retries the failures that were caused by a transient outage, and exposes the
last 24 hours to the settings page.

The table is bounded on purpose: events older than ``KEEP_DAYS`` are pruned,
and a pending row is dropped after ``RETRY_DELAYS`` is exhausted, so a broken
push target cannot grow the database.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from backend.db import PushEvent, PushPending, SessionLocal

logger = logging.getLogger("board-manager")

KEEP_DAYS = 7
# Backoff between post-failure retries. Three retries covers a phone that is
# briefly offline or a Wi-Fi handover; beyond that the alert is stale anyway.
RETRY_DELAYS = (60, 300, 900)
RETRY_INTERVAL_SECONDS = 45


def _now() -> int:
    return int(time.time())


def record(channel: str, ok: bool, title: str = "", error: str = "") -> None:
    """Store one delivery attempt. Never raises into the notify path."""
    try:
        db = SessionLocal()
        try:
            db.add(PushEvent(ts=_now(), channel=channel, ok=1 if ok else 0,
                             title=(title or "")[:160], error=(error or "")[:255]))
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.debug("push event record failed", exc_info=True)


def enqueue(title: str, body: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Queue a notification that already failed its inline retries."""
    try:
        db = SessionLocal()
        try:
            now = _now()
            db.add(PushPending(
                created=now, next_ts=now + RETRY_DELAYS[0],
                title=(title or "")[:160], body=body or "",
                extra=json.dumps(extra or {}, ensure_ascii=False),
                attempts=0, status="pending",
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.debug("push enqueue failed", exc_info=True)


def prune() -> None:
    """Drop old events and finished queue rows."""
    try:
        db = SessionLocal()
        try:
            db.query(PushEvent).filter(PushEvent.ts < _now() - KEEP_DAYS * 86400).delete(
                synchronize_session=False)
            db.query(PushPending).filter(
                PushPending.status != "pending",
                PushPending.created < _now() - 2 * 86400,
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.debug("push prune failed", exc_info=True)


def stats(hours: int = 24) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        since = _now() - max(1, hours) * 3600
        rows = db.query(PushEvent).filter(PushEvent.ts >= since).all()
        ok = sum(1 for r in rows if r.ok)
        fail = len(rows) - ok
        last_ok = max((r.ts for r in rows if r.ok), default=0)
        last_fail_row = next(
            (r for r in sorted(rows, key=lambda x: x.ts, reverse=True) if not r.ok), None)
        pending = db.query(PushPending).filter(PushPending.status == "pending").count()
        dropped = db.query(PushPending).filter(
            PushPending.status == "dropped", PushPending.created >= since).count()
        last_error = (last_fail_row.error if last_fail_row else "") or ""
        return {
            "window_hours": hours,
            "ok": ok,
            "fail": fail,
            "total": len(rows),
            "pending": pending,
            "dropped": dropped,
            "last_ok_ts": last_ok,
            "last_error": last_error,
        }
    finally:
        db.close()


def retry_due(limit: int = 5) -> int:
    """Re-send queued notifications whose backoff has expired."""
    # Imported here: messages imports this module, so a top-level import
    # would be circular.
    from backend.messages import send_bark

    db = SessionLocal()
    sent = 0
    try:
        rows = (
            db.query(PushPending)
            .filter(PushPending.status == "pending", PushPending.next_ts <= _now())
            .order_by(PushPending.next_ts.asc())
            .limit(limit)
            .all()
        )
        for row in rows:
            try:
                extra = json.loads(row.extra or "{}")
            except Exception:
                extra = {}
            ok = send_bark(row.title, row.body, None, extra or None, _from_queue=True)
            row.attempts = (row.attempts or 0) + 1
            if ok:
                row.status = "done"
                sent += 1
            elif row.attempts >= len(RETRY_DELAYS):
                row.status = "dropped"
                row.error = "重试 3 次仍未送达"
            else:
                row.next_ts = _now() + RETRY_DELAYS[row.attempts]
            row.error = "" if ok else (row.error or "retry failed")
        db.commit()
    except Exception:
        db.rollback()
        logger.debug("push retry failed", exc_info=True)
    finally:
        db.close()
    return sent


async def push_retry_loop() -> None:
    """Retry queued pushes and prune the tables once in a while."""
    tick = 0
    while True:
        try:
            await asyncio.to_thread(retry_due)
            if tick % 40 == 0:
                await asyncio.to_thread(prune)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("push retry loop error", exc_info=True)
        tick += 1
        await asyncio.sleep(RETRY_INTERVAL_SECONDS)
