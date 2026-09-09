"""Leakage-safe historical system snapshot reconstruction."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.services.replay_service import build_replay_snapshot, parse_bbox
from backend.app.services.runtime_replay_cache import RuntimeReplayCache


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/replay", response_model=ReplaySnapshotResponse)
def get_replay_snapshot(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    bbox: str = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    try:
        cutoff = datetime.strptime(date, "%Y-%m-%d").date()
        parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid replay request: {exc}")

    cache = RuntimeReplayCache.for_session(db)
    cached = cache.load(date=date, bbox=bbox, limit=limit)
    if cached is not None:
        return cached.model_copy(update={"cache_status": "HIT"})

    try:
        result = build_replay_snapshot(db, cutoff=cutoff, bbox=bbox, limit=limit)
    except Exception as exc:
        logger.exception("Historical replay failed for %s", date)
        raise HTTPException(status_code=503, detail=f"Replay reconstruction failed: {exc}")

    cache.store(date=date, bbox=bbox, limit=limit, response=result)
    return result
