"""
Asynchronous Prithvi Foundation Model & HLS Imagery Worker Queue
Processes high-priority alerted sites and A-Core uncertain sites in the background,
evaluating optical/infrared patches and executing guarded rescues without blocking web requests.
"""

import asyncio
import logging
from typing import Set, Optional
from datetime import datetime, date, timezone

from backend.app.db.session import SessionLocal
from backend.app.db.models import SourceSite, SiteModelA, SiteModelB, SiteModelC, Alert
from backend.app.services.imagery_service import get_or_create_site_imagery, PRITHVI_RESCUE_THRESHOLD
from backend.app.engines.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)

# In-memory queue and active tracking set
_prithvi_queue: Optional[asyncio.Queue] = None
_enqueued_sites: Set[str] = set()
_worker_task: Optional[asyncio.Task] = None
_decision_engine = DecisionEngine()


def get_prithvi_queue() -> asyncio.Queue:
    global _prithvi_queue
    if _prithvi_queue is None:
        _prithvi_queue = asyncio.Queue()
    return _prithvi_queue


def enqueue_site_for_prithvi(site_id: str) -> bool:
    """
    Enqueues a site for background HLS download and Prithvi scoring.
    Returns True if newly added, False if already queued.
    """
    if site_id in _enqueued_sites:
        return False

    queue = get_prithvi_queue()
    _enqueued_sites.add(site_id)
    try:
        queue.put_nowait(site_id)
        logger.info(f"Enqueued site '{site_id}' for background Prithvi visual scoring.")
        return True
    except Exception as e:
        logger.error(f"Failed to enqueue site '{site_id}': {e}")
        _enqueued_sites.discard(site_id)
        return False


def get_prithvi_queue_stats() -> dict:
    """Returns current queue metrics."""
    q = get_prithvi_queue()
    return {
        "pending_tasks": q.qsize(),
        "total_enqueued": len(_enqueued_sites),
        "worker_running": _worker_task is not None and not _worker_task.done()
    }


async def prithvi_worker_loop():
    """
    Continuous background consumer processing queued sites.
    """
    queue = get_prithvi_queue()
    logger.info("Asynchronous Prithvi background worker loop started.")

    while True:
        try:
            site_id = await queue.get()
            try:
                # Run synchronous imagery & Prithvi inference in threadpool
                loop = asyncio.get_running_loop()
                await loop.run_in_threadpool(_process_single_site, site_id)
            except Exception as e:
                logger.error(f"Error processing Prithvi background task for site '{site_id}': {e}")
            finally:
                _enqueued_sites.discard(site_id)
                queue.task_done()
        except asyncio.CancelledError:
            logger.info("Prithvi worker loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in Prithvi worker: {e}")
            await asyncio.sleep(1.0)


def _process_single_site(site_id: str):
    """
    Synchronous processor executed in threadpool to avoid blocking event loop.
    """
    db = SessionLocal()
    try:
        site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
        if not site:
            return

        model_a = db.query(SiteModelA).filter(SiteModelA.site_id == site_id).first()
        prev_decision = model_a.decision if model_a else None

        # Fetch satellite patch, compute spectral channels, and run Prithvi ViT scoring
        imagery_summary = get_or_create_site_imagery(db, site_id)

        # Check if guarded rescue occurred
        db.refresh(model_a)
        if model_a and model_a.decision == "INDUSTRIAL_PRITHVI_RESCUE" and prev_decision != "INDUSTRIAL_PRITHVI_RESCUE":
            logger.info(f"SITE RESCUED: Site '{site_id}' promoted to INDUSTRIAL_PRITHVI_RESCUE by Prithvi score {imagery_summary.prithvi_probability}!")
            
            # Re-evaluate Decision Engine to escalate alert
            mb = db.query(SiteModelB).filter(SiteModelB.site_id == site_id).first()
            mc = db.query(SiteModelC).filter(SiteModelC.site_id == site_id).first()
            existing_alert = (
                db.query(Alert)
                .filter(Alert.site_id == site_id, Alert.status == "ACTIVE")
                .order_by(Alert.created_at.desc())
                .first()
            )

            today_str = date.today().isoformat()
            alert_dict = _decision_engine.evaluate(
                site_id=site_id,
                site_day=today_str,
                model_a_class=model_a.class_name,
                model_b_state=mb.state if mb else "DORMANT",
                model_c_status=mc.operational_status if mc else "INSUFFICIENT_HISTORY",
                model_c_score=mc.c_score if mc else None,
                existing_alert=existing_alert
            )

            if alert_dict and alert_dict.get("alert_level") not in ("NONE", "INFO"):
                now_utc = datetime.now(timezone.utc)
                if existing_alert and existing_alert.fingerprint == alert_dict.get("fingerprint"):
                    existing_alert.alert_level = alert_dict["alert_level"]
                    existing_alert.alert_type = alert_dict["alert_type"]
                    existing_alert.headline = alert_dict["headline"]
                    existing_alert.updated_at = now_utc
                else:
                    new_alert = Alert(
                        alert_id=alert_dict["alert_id"],
                        site_id=site_id,
                        site_day=date.today(),
                        alert_type=alert_dict["alert_type"],
                        alert_level=alert_dict["alert_level"],
                        headline=alert_dict["headline"],
                        reason_codes=alert_dict.get("reason_codes"),
                        evidence_required=alert_dict.get("evidence_required", False),
                        fingerprint=alert_dict["fingerprint"],
                        status="ACTIVE",
                        is_escalation=alert_dict.get("is_escalation", False),
                        created_at=now_utc,
                        updated_at=now_utc
                    )
                    db.add(new_alert)
                db.commit()
                logger.info(f"Dispatched escalated operational alert for rescued site '{site_id}'!")
    finally:
        db.close()


def start_prithvi_worker():
    """Starts the background worker task."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(prithvi_worker_loop())


def stop_prithvi_worker():
    """Stops the background worker task."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
