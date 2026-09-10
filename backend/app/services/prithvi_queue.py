"""Asynchronous, fail-closed HLS/Prithvi evidence queue."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Set

import numpy as np

from backend.app.db.models import Alert, ImageryCache, SiteModelA, SiteModelB, SiteModelC, SourceSite
from backend.app.db.session import SessionLocal
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.services.hls_service import HLSCloudRejected, HLSService, HLSUnavailable
from backend.app.services.model_a_service import ModelAService
from backend.app.services.prithvi_service import PrithviService, PrithviUnavailable
from backend.app.services.stack_readiness import get_shared_model_a


logger = logging.getLogger(__name__)
_queue: Optional[asyncio.Queue[str]] = None
_enqueued: Set[str] = set()
_worker_task: Optional[asyncio.Task] = None


def get_prithvi_queue() -> asyncio.Queue[str]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


def enqueue_site_for_prithvi(site_id: str) -> bool:
    if site_id in _enqueued:
        return False
    _enqueued.add(site_id)
    try:
        get_prithvi_queue().put_nowait(site_id)
        return True
    except Exception:
        _enqueued.discard(site_id)
        raise


def get_prithvi_queue_stats() -> dict:
    queue = get_prithvi_queue()
    return {
        "pending_tasks": queue.qsize(),
        "total_enqueued": len(_enqueued),
        "worker_running": _worker_task is not None and not _worker_task.done(),
    }


async def prithvi_worker_loop() -> None:
    queue = get_prithvi_queue()
    while True:
        try:
            site_id = await queue.get()
            try:
                await asyncio.to_thread(_process_single_site, site_id)
            except Exception:
                logger.exception("Prithvi task failed for %s", site_id)
            finally:
                _enqueued.discard(site_id)
                queue.task_done()
        except asyncio.CancelledError:
            break


def _process_single_site(site_id: str) -> None:
    db = SessionLocal()
    try:
        site = db.query(SourceSite).filter_by(site_id=site_id).one_or_none()
        model_a = db.query(SiteModelA).filter_by(site_id=site_id).one_or_none()
        if site is None or model_a is None:
            return
        core_engine = get_shared_model_a()
        if not core_engine.thresh_low <= float(model_a.core_probability) < core_engine.thresh_core:
            return

        acquisition_date = site.latest_seen or date.today()
        started_at = time.perf_counter()
        logger.info(
            "Prithvi task started for %s (target date %s)", site_id, acquisition_date
        )
        try:
            prithvi = PrithviService()
            patch = HLSService().get_or_fetch_patch(
                site_id, site.latitude, site.longitude, acquisition_date
            )
            result = prithvi.score(patch)
        except HLSCloudRejected as exc:
            _persist_unavailable(
                db, site_id, acquisition_date, str(exc), status="REJECTED_CLOUD"
            )
            model_a.prithvi_probability = None
            model_a.prithvi_status = "REJECTED_CLOUD"
            db.commit()
            return
        except (HLSUnavailable, PrithviUnavailable, ValueError) as exc:
            _persist_unavailable(db, site_id, acquisition_date, str(exc), status="UNAVAILABLE")
            model_a.prithvi_probability = None
            model_a.prithvi_status = "UNAVAILABLE"
            db.commit()
            return

        acquisition_date = patch.acquisition_date
        previous_decision = model_a.decision
        current_a = ModelAService().score_site(
            db,
            site_id,
            prithvi_probability=result.probability,
            imagery_acquisition_date=acquisition_date,
        )
        cache = db.query(ImageryCache).filter_by(
            site_id=site_id, acquisition_date=acquisition_date
        ).one_or_none()
        if cache is None:
            cache = ImageryCache(
                cache_id=f"HLS_{site_id}_{acquisition_date.isoformat()}",
                site_id=site_id,
                acquisition_date=acquisition_date,
            )
            db.add(cache)
        cache.prithvi_probability = result.probability
        cache.hls_product = patch.product
        cache.cloud_fraction = patch.cloud_fraction
        cache.source_uri = patch.source_uri
        cache.patch_uri = patch.cache_path
        cache.embedding_uri = _persist_embedding(site_id, acquisition_date, result.embedding)
        cache.model_revision = result.model_revision
        cache.failure_reason = None
        cache.status = "AVAILABLE"
        cache.updated_at = datetime.now(timezone.utc)

        if current_a["decision"] != previous_decision:
            _rerun_decision(db, site_id, current_a)
        db.commit()
        logger.info(
            "Prithvi task completed for %s: probability=%.6f decision=%s elapsed=%.1fs",
            site_id,
            result.probability,
            current_a["decision"],
            time.perf_counter() - started_at,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persist_unavailable(
    db, site_id: str, acquisition_date: date, reason: str, status: str
) -> None:
    cache = db.query(ImageryCache).filter_by(
        site_id=site_id, acquisition_date=acquisition_date
    ).one_or_none()
    if cache is None:
        cache = ImageryCache(
            cache_id=f"HLS_{site_id}_{acquisition_date.isoformat()}",
            site_id=site_id,
            acquisition_date=acquisition_date,
        )
        db.add(cache)
    cache.status = status
    cache.prithvi_probability = None
    cache.failure_reason = reason[:4000]
    cache.patch_uri = None
    cache.embedding_uri = None
    cache.model_revision = None
    cache.updated_at = datetime.now(timezone.utc)
    logger.info("Imagery unavailable for %s: %s", site_id, reason)


def _persist_embedding(site_id: str, acquisition_date: date, embedding: np.ndarray) -> str:
    root = Path(os.environ.get("PRITHVI_CACHE_DIR", "data/cache/prithvi"))
    directory = root / site_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{acquisition_date.isoformat()}.npy"
    temporary = target.with_suffix(".npy.tmp")
    with temporary.open("wb") as handle:
        np.save(handle, np.asarray(embedding, dtype=np.float32), allow_pickle=False)
    temporary.replace(target)
    return str(target)


def _rerun_decision(db, site_id: str, model_a_result: dict) -> None:
    mb = db.query(SiteModelB).filter_by(site_id=site_id).one_or_none()
    mc = db.query(SiteModelC).filter_by(site_id=site_id).one_or_none()
    if mb is None or mc is None:
        return
    site_day = mc.event_date or date.today()
    existing = (
        db.query(Alert)
        .filter(Alert.site_id == site_id, Alert.site_day == site_day, Alert.status == "ACTIVE")
        .order_by(Alert.created_at.desc())
        .first()
    )
    existing_payload = None
    if existing:
        existing_payload = {
            "alert_level": existing.alert_level,
            "alert_type": existing.alert_type,
            "created_at": existing.created_at.isoformat(),
        }
    alert = DecisionEngine().evaluate(
        site_id=site_id,
        site_day=site_day.isoformat(),
        model_a_result={"decision": model_a_result["decision"]},
        model_b_result={"state": mb.state, "confidence": mb.confidence},
        model_c_result={"status": mc.operational_status, "c_score": mc.c_score},
        existing_alert=existing_payload,
    )
    if alert["alert_level"] in ("NONE", "INFO"):
        return
    fingerprint = alert["alert_fingerprint"]
    row = db.query(Alert).filter_by(fingerprint=fingerprint).one_or_none()
    if row is None:
        row = Alert(
            alert_id=f"ALT_{uuid.uuid4().hex}",
            site_id=site_id,
            site_day=site_day,
            fingerprint=fingerprint,
            status="ACTIVE",
        )
        db.add(row)
    row.alert_type = alert["alert_type"]
    row.alert_level = alert["alert_level"]
    row.headline = alert["headline"]
    row.reason_codes = alert["reason_codes"]
    row.evidence_required = alert["evidence_required"]
    row.is_escalation = alert["is_escalation"]
    row.updated_at = datetime.now(timezone.utc)


def start_prithvi_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(prithvi_worker_loop())


def stop_prithvi_worker() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
    _worker_task = None
