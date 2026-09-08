"""Read-only access to genuine cached HLS/Prithvi evidence.

This module deliberately contains no RGB-to-HLS conversion, procedural fallback,
or probability heuristic. Missing evidence remains missing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from backend.app.db.models import ImageryCache
from backend.app.schemas.evidence import ImageryCacheSummary


CACHE_DIR = os.environ.get("HLS_CACHE_DIR", str(Path("data") / "cache" / "hls"))


def get_site_imagery_cache(db: Session, site_id: str) -> List[ImageryCacheSummary]:
    rows = (
        db.query(ImageryCache)
        .filter(ImageryCache.site_id == site_id)
        .order_by(ImageryCache.acquisition_date.desc())
        .all()
    )
    return [
        ImageryCacheSummary(
            cache_id=row.cache_id,
            site_id=row.site_id,
            acquisition_date=str(row.acquisition_date),
            product=row.hls_product or "HLS",
            cloud_fraction=row.cloud_fraction,
            prithvi_probability=row.prithvi_probability,
            status=row.status,
            source_uri=row.source_uri,
            patch_uri=row.patch_uri,
            embedding_uri=row.embedding_uri,
            model_revision=row.model_revision,
            failure_reason=row.failure_reason,
        )
        for row in rows
    ]
