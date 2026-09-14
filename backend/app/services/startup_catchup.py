"""Non-blocking startup catch-up for a stale operational stack."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.stack_readiness import StackReadinessReport, run_stack_preflight


logger = logging.getLogger(__name__)
_ADVISORY_LOCK_ID = 261622026
_task: Optional[asyncio.Task] = None
_status: Dict[str, Any] = {
    "status": "IDLE",
    "running": False,
    "phase": "IDLE",
    "progress_percent": 0,
    "source_date": None,
    "target_date": None,
    "completed_windows": 0,
    "total_windows": 0,
    "current_window_start": None,
    "current_window_end": None,
    "records_processed": 0,
    "processed_sites": 0,
    "total_sites": 0,
    "started_at": None,
    "ended_at": None,
    "detail": "No startup catch-up has been requested.",
}


def get_startup_catchup_status() -> Dict[str, Any]:
    return dict(_status)


def should_start_startup_catchup(readiness: StackReadinessReport) -> bool:
    return (
        readiness.status == "STALE_BACKFILL"
        and os.environ.get("AUTO_STARTUP_CATCHUP", "true").lower() == "true"
        and bool(os.environ.get("FIRMS_MAP_KEY", "").strip())
    )


def start_startup_catchup(app) -> asyncio.Task:
    """Start one catch-up task without delaying FastAPI availability."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_catch_up_and_activate(app))
    return _task


async def _catch_up_and_activate(app) -> None:
    target = max(date(2026, 1, 1), date.today() - timedelta(days=1))
    _status.update({
        "status": "RUNNING",
        "running": True,
        "phase": "ACQUIRING_LOCK",
        "progress_percent": 1,
        "source_date": "2026-01-01",
        "target_date": target.isoformat(),
        "completed_windows": 0,
        "total_windows": 0,
        "current_window_start": None,
        "current_window_end": None,
        "records_processed": 0,
        "processed_sites": 0,
        "total_sites": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "detail": "Catching up FIRMS and publishing the current A/B/C snapshot.",
    })
    logger.info(
        "Runtime stack is stale; starting background FIRMS catch-up through %s.",
        target,
    )
    try:
        result = await asyncio.to_thread(
            _run_locked_catchup, target, _update_catchup_progress
        )
        if result.get("status") == "SKIPPED_ALREADY_RUNNING":
            _status.update({
                "status": "SKIPPED_ALREADY_RUNNING",
                "running": False,
                "phase": "LOCKED_BY_PEER",
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "detail": "Another backend process owns the database catch-up lock.",
            })
            return

        db = SessionLocal()
        try:
            readiness = run_stack_preflight(db)
        finally:
            db.close()
        app.state.stack_readiness = readiness.to_dict()
        if readiness.can_start_live:
            from backend.app.services.scheduler import start_scheduler

            start_scheduler()
            _status.update({
                "status": "COMPLETED",
                "running": False,
                "phase": "LIVE_ACTIVATED",
                "progress_percent": 100,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "detail": (
                    f"Catch-up published {result.get('snapshot_status')} through {target}; "
                    "live scheduler started."
                ),
            })
            logger.info("Startup catch-up completed; runtime readiness is %s.", readiness.status)
        else:
            _status.update({
                "status": "COMPLETED_NOT_READY",
                "running": False,
                "phase": "READINESS_BLOCKED",
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "detail": f"Catch-up completed but readiness is {readiness.status}: {readiness.detail}",
            })
            logger.warning(_status["detail"])
    except Exception as exc:
        detail = _safe_error_detail(exc)
        _status.update({
            "status": "FAILED",
            "running": False,
            "phase": "FAILED",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
        })
        logger.error("Automatic startup catch-up failed: %s", detail)


def _update_catchup_progress(payload: Dict[str, Any]) -> None:
    """Receive thread-safe primitive progress fields from the backfill worker."""
    _status.update(payload)


def _run_locked_catchup(target: date, progress_callback=None) -> Dict[str, Any]:
    """Run catch-up under a session-level PostgreSQL advisory lock."""
    lock_db = SessionLocal()
    acquired = True
    is_postgres = lock_db.get_bind().dialect.name == "postgresql"
    try:
        if is_postgres:
            acquired = bool(
                lock_db.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": _ADVISORY_LOCK_ID},
                ).scalar()
            )
        if not acquired:
            return {"status": "SKIPPED_ALREADY_RUNNING"}
        return BackfillOrchestrator().run_backfill(
            start_date="2026-01-01",
            end_date=target.isoformat(),
            update_db=True,
            progress_callback=progress_callback,
        )
    finally:
        if is_postgres and acquired:
            try:
                lock_db.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _ADVISORY_LOCK_ID},
                )
            except Exception:
                logger.exception("Could not release the startup catch-up advisory lock")
        lock_db.close()


def _safe_error_detail(exc: Exception) -> str:
    detail = str(exc)
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if map_key:
        detail = detail.replace(map_key, "[REDACTED]")
    return detail
