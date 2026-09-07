"""
Background Polling Scheduler & Cron Maintenance Service
Manages the 15-minute NASA FIRMS NRT polling cycle, the daily global Model B temporal decay job,
and the asynchronous Prithvi worker queue using APScheduler.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.services.firms_client import FirmsClient, DEFAULT_INDIA_BBOX, DEFAULT_PRIMARY_SOURCE
from backend.app.services.live_pipeline import get_live_pipeline_service, run_global_daily_model_b_refresh
from backend.app.services.prithvi_queue import start_prithvi_worker, stop_prithvi_worker, get_prithvi_queue_stats

logger = logging.getLogger(__name__)

# Configurable intervals
POLL_MINUTES = int(os.environ.get("FIRMS_POLL_MINUTES", "15"))

_scheduler: Optional[AsyncIOScheduler] = None
_telemetry = {
    "is_running": False,
    "started_at": None,
    "last_poll_at": None,
    "last_poll_status": "NONE",
    "last_records_read": 0,
    "last_alerts_generated": 0,
    "last_decay_at": None,
    "poll_interval_minutes": POLL_MINUTES,
    "total_poll_cycles": 0
}


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def poll_firms_nrt_job():
    """
    15-minute scheduled job to fetch latest FIRMS NOAA-20 NRT active fires
    and run the incremental resolution & rescoring pipeline.
    """
    global _telemetry
    logger.info("Executing scheduled 15-minute NASA FIRMS NRT polling cycle...")
    t0 = datetime.now(timezone.utc)
    _telemetry["total_poll_cycles"] += 1

    client = FirmsClient()
    pipeline = get_live_pipeline_service()

    try:
        # Run network I/O in threadpool
        loop = asyncio.get_running_loop()
        records = await loop.run_in_threadpool(
            client.fetch_area,
            source=DEFAULT_PRIMARY_SOURCE,
            bbox=DEFAULT_INDIA_BBOX,
            day_range=1
        )

        db = SessionLocal()
        try:
            res = await loop.run_in_threadpool(
                pipeline.process_detections_batch,
                raw_records=records,
                db=db,
                source_sensor=DEFAULT_PRIMARY_SOURCE
            )
            _telemetry["last_poll_at"] = t0.isoformat()
            _telemetry["last_poll_status"] = "SUCCESS"
            _telemetry["last_records_read"] = len(records)
            _telemetry["last_alerts_generated"] = res.get("alerts_generated", 0)
            logger.info(f"FIRMS NRT cycle complete: {len(records)} read, {res.get('alerts_generated', 0)} alerts.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"FIRMS NRT polling encountered non-fatal error: {e}")
        _telemetry["last_poll_at"] = t0.isoformat()
        _telemetry["last_poll_status"] = f"ERROR: {str(e)}"


async def daily_model_b_refresh_job():
    """
    Daily maintenance job executed at 00:05 UTC.
    Decays Model B temporal states for sites with no activity on the previous date.
    """
    global _telemetry
    logger.info("Executing daily Model B temporal decay refresh...")
    loop = asyncio.get_running_loop()
    db = SessionLocal()
    try:
        res = await loop.run_in_threadpool(
            run_global_daily_model_b_refresh,
            db=db,
            as_of_date=date.today()
        )
        _telemetry["last_decay_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Daily Model B refresh complete: {res.get('decayed_to_dormant', 0)} sites decayed.")
    except Exception as e:
        logger.error(f"Error during daily Model B decay: {e}")
    finally:
        db.close()


def start_scheduler():
    """Starts APScheduler and the asynchronous Prithvi worker."""
    global _scheduler, _telemetry
    scheduler = get_scheduler()

    if not scheduler.running:
        # 1. 15-minute FIRMS NRT polling job
        scheduler.add_job(
            poll_firms_nrt_job,
            trigger=IntervalTrigger(minutes=POLL_MINUTES),
            id="firms_nrt_poll",
            name="15-min NASA FIRMS NRT Ingestion",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )

        # 2. Daily midnight Model B decay cron (00:05 UTC)
        scheduler.add_job(
            daily_model_b_refresh_job,
            trigger=CronTrigger(hour=0, minute=5, timezone=timezone.utc),
            id="daily_model_b_decay",
            name="Daily Model B Temporal State Decay",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )

        scheduler.start()
        _telemetry["is_running"] = True
        _telemetry["started_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"APScheduler started with {len(scheduler.get_jobs())} jobs (interval: {POLL_MINUTES}m).")

    # Start asynchronous background Prithvi worker
    start_prithvi_worker()


def stop_scheduler():
    """Gracefully shuts down APScheduler and the Prithvi worker."""
    global _scheduler, _telemetry
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _telemetry["is_running"] = False
        logger.info("APScheduler stopped.")
    stop_prithvi_worker()


def get_scheduler_status() -> Dict[str, Any]:
    """Returns complete operational status of scheduler and async queues."""
    sched = get_scheduler()
    jobs_info = []
    if sched and sched.running:
        for j in sched.get_jobs():
            next_run = j.next_run_time.isoformat() if j.next_run_time else None
            jobs_info.append({
                "job_id": j.id,
                "job_name": j.name,
                "next_run_time": next_run
            })

    prithvi_stats = get_prithvi_queue_stats()

    return {
        "scheduler": {
            **_telemetry,
            "jobs": jobs_info
        },
        "prithvi_queue": prithvi_stats
    }


async def trigger_manual_poll(db: Session) -> Dict[str, Any]:
    """Manual on-demand trigger to fetch FIRMS and execute the pipeline immediately."""
    client = FirmsClient()
    pipeline = get_live_pipeline_service()

    loop = asyncio.get_running_loop()
    records = await loop.run_in_threadpool(
        client.fetch_area,
        source=DEFAULT_PRIMARY_SOURCE,
        bbox=DEFAULT_INDIA_BBOX,
        day_range=1
    )

    res = await loop.run_in_threadpool(
        pipeline.process_detections_batch,
        raw_records=records,
        db=db,
        source_sensor=DEFAULT_PRIMARY_SOURCE
    )
    return res


async def trigger_manual_decay(db: Session) -> Dict[str, Any]:
    """Manual on-demand trigger for daily Model B decay."""
    loop = asyncio.get_running_loop()
    res = await loop.run_in_threadpool(
        run_global_daily_model_b_refresh,
        db=db,
        as_of_date=date.today()
    )
    return res
