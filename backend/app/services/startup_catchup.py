"""Non-blocking startup catch-up for a stale operational stack."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.stack_readiness import StackReadinessReport, run_stack_preflight


logger = logging.getLogger(__name__)
_ADVISORY_LOCK_ID = 261622026
_task: Optional[asyncio.Task] = None
_status_lock = threading.RLock()
_last_terminal_detail: Optional[str] = None
_status: Dict[str, Any] = {
    "status": "IDLE",
    "running": False,
    "phase": "IDLE",
    "progress_percent": 0,
    "phase_progress_percent": 0,
    "source_date": None,
    "target_date": None,
    "completed_windows": 0,
    "total_windows": 0,
    "current_window_start": None,
    "current_window_end": None,
    "records_processed": 0,
    "records_fetched": 0,
    "records_unique": 0,
    "records_revised": 0,
    "promoted_sites": 0,
    "alerts_generated": 0,
    "current_source": None,
    "model_b_processed_sites": 0,
    "model_b_total_sites": 0,
    "worldcover_processed_sites": 0,
    "worldcover_total_sites": 0,
    "worldcover_current_tile": None,
    "processed_sites": 0,
    "total_sites": 0,
    "started_at": None,
    "ended_at": None,
    "updated_at": None,
    "elapsed_seconds": 0,
    "estimated_remaining_seconds": None,
    "estimated_completion_at": None,
    "progress_rate_percent_per_minute": None,
    "activity_log": [],
    "detail": "No startup catch-up has been requested.",
}


def get_startup_catchup_status() -> Dict[str, Any]:
    with _status_lock:
        status = dict(_status)
        status["activity_log"] = list(_status.get("activity_log", []))
    status.update(_calculate_runtime_metrics(status))
    return status


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _calculate_runtime_metrics(status: Dict[str, Any]) -> Dict[str, Any]:
    started = _parse_timestamp(status.get("started_at"))
    if started is None:
        return {
            "elapsed_seconds": 0,
            "estimated_remaining_seconds": None,
            "estimated_completion_at": None,
            "progress_rate_percent_per_minute": None,
        }
    ended = _parse_timestamp(status.get("ended_at"))
    now = ended or datetime.now(timezone.utc)
    elapsed = max(0, round((now - started).total_seconds()))
    progress = max(0.0, min(100.0, float(status.get("progress_percent") or 0)))
    rate = round(progress / elapsed * 60, 3) if elapsed > 0 and progress > 0 else None
    remaining = None
    completion = None
    if status.get("running") and elapsed >= 2 and 1 < progress < 100:
        remaining = max(0, round(elapsed * (100 - progress) / progress))
        completion = (now + timedelta(seconds=remaining)).isoformat()
    elif status.get("status") == "COMPLETED":
        remaining = 0
        completion = ended.isoformat() if ended else now.isoformat()
    return {
        "elapsed_seconds": elapsed,
        "estimated_remaining_seconds": remaining,
        "estimated_completion_at": completion,
        "progress_rate_percent_per_minute": rate,
    }


def _append_activity_unlocked(
    message: str,
    *,
    phase: Optional[str] = None,
    level: str = "INFO",
    timestamp: Optional[str] = None,
) -> None:
    if not message:
        return
    activity = list(_status.get("activity_log", []))
    if activity and activity[-1].get("message") == message:
        return
    activity.append({
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "phase": phase or str(_status.get("phase") or "STARTUP"),
        "level": level,
        "message": message,
    })
    _status["activity_log"] = activity[-20:]


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
    global _last_terminal_detail
    _last_terminal_detail = None
    target = max(date(2026, 1, 1), date.today() - timedelta(days=1))
    started_at = datetime.now(timezone.utc).isoformat()
    initial_detail = "Catching up FIRMS and publishing the current A/B/C snapshot."
    with _status_lock:
        _status.update({
            "status": "RUNNING",
            "running": True,
            "phase": "ACQUIRING_LOCK",
            "progress_percent": 1,
            "phase_progress_percent": 0,
            "source_date": "2026-01-01",
            "target_date": target.isoformat(),
            "completed_windows": 0,
            "total_windows": 0,
            "current_window_start": None,
            "current_window_end": None,
            "records_processed": 0,
            "records_fetched": 0,
            "records_unique": 0,
            "records_revised": 0,
            "promoted_sites": 0,
            "alerts_generated": 0,
            "current_source": None,
            "model_b_processed_sites": 0,
            "model_b_total_sites": 0,
            "worldcover_processed_sites": 0,
            "worldcover_total_sites": 0,
            "worldcover_current_tile": None,
            "processed_sites": 0,
            "total_sites": 0,
            "started_at": started_at,
            "ended_at": None,
            "updated_at": started_at,
            "elapsed_seconds": 0,
            "estimated_remaining_seconds": None,
            "estimated_completion_at": None,
            "progress_rate_percent_per_minute": None,
            "activity_log": [],
            "detail": initial_detail,
        })
        _append_activity_unlocked(initial_detail, timestamp=started_at)
    logger.info(
        "Runtime stack is stale; starting background FIRMS catch-up through %s.",
        target,
    )
    try:
        result = await asyncio.to_thread(
            _run_locked_catchup, target, _update_catchup_progress
        )
        if result.get("status") == "SKIPPED_ALREADY_RUNNING":
            ended_at = datetime.now(timezone.utc).isoformat()
            detail = "Another backend process owns the database catch-up lock."
            with _status_lock:
                _status.update({
                    "status": "SKIPPED_ALREADY_RUNNING",
                    "running": False,
                    "phase": "LOCKED_BY_PEER",
                    "phase_progress_percent": 0,
                    "ended_at": ended_at,
                    "updated_at": ended_at,
                    "detail": detail,
                })
                _append_activity_unlocked(detail, level="WARNING", timestamp=ended_at)
            logger.warning(detail)
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
            ended_at = datetime.now(timezone.utc).isoformat()
            detail = (
                f"Catch-up published {result.get('snapshot_status')} through {target}; "
                "live scheduler started."
            )
            with _status_lock:
                _status.update({
                    "status": "COMPLETED",
                    "running": False,
                    "phase": "LIVE_ACTIVATED",
                    "progress_percent": 100,
                    "phase_progress_percent": 100,
                    "ended_at": ended_at,
                    "updated_at": ended_at,
                    "detail": detail,
                })
                _append_activity_unlocked(detail, timestamp=ended_at)
            logger.info("Startup catch-up completed; runtime readiness is %s.", readiness.status)
        else:
            ended_at = datetime.now(timezone.utc).isoformat()
            detail = f"Catch-up completed but readiness is {readiness.status}: {readiness.detail}"
            with _status_lock:
                _status.update({
                    "status": "COMPLETED_NOT_READY",
                    "running": False,
                    "phase": "READINESS_BLOCKED",
                    "phase_progress_percent": 100,
                    "ended_at": ended_at,
                    "updated_at": ended_at,
                    "detail": detail,
                })
                _append_activity_unlocked(detail, level="WARNING", timestamp=ended_at)
            logger.warning(detail)
    except Exception as exc:
        detail = _safe_error_detail(exc)
        ended_at = datetime.now(timezone.utc).isoformat()
        with _status_lock:
            _status.update({
                "status": "FAILED",
                "running": False,
                "phase": "FAILED",
                "phase_progress_percent": 0,
                "ended_at": ended_at,
                "updated_at": ended_at,
                "detail": detail,
            })
            _append_activity_unlocked(detail, level="ERROR", timestamp=ended_at)
        logger.error("Automatic startup catch-up failed: %s", detail)


def _update_catchup_progress(payload: Dict[str, Any]) -> None:
    """Receive thread-safe primitive progress fields from the backfill worker."""
    global _last_terminal_detail
    next_payload = dict(payload)
    updated_at = datetime.now(timezone.utc).isoformat()
    next_payload["updated_at"] = updated_at
    with _status_lock:
        _status.update(next_payload)
        detail = str(_status.get("detail") or "")
        phase = str(_status.get("phase") or "STARTUP")
        _append_activity_unlocked(detail, phase=phase, timestamp=updated_at)
        snapshot = dict(_status)
    metrics = _calculate_runtime_metrics(snapshot)
    with _status_lock:
        _status.update(metrics)

    if detail and detail != _last_terminal_detail:
        _last_terminal_detail = detail
        eta = metrics.get("estimated_remaining_seconds")
        eta_text = _format_duration(eta) if eta is not None else "estimating"
        logger.info(
            "Startup progress | overall=%s%% phase=%s phase_progress=%s%% "
            "elapsed=%s eta~%s | %s",
            snapshot.get("progress_percent", 0),
            phase,
            snapshot.get("phase_progress_percent", 0),
            _format_duration(metrics.get("elapsed_seconds", 0)),
            eta_text,
            detail,
        )


def _format_duration(seconds: Any) -> str:
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


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
