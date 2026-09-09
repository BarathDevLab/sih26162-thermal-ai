"""Small local cache for immutable historical replay responses."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.schemas.replay import ReplaySnapshotResponse


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
CACHE_SCHEMA_VERSION = "2"


class RuntimeReplayCache:
    def __init__(self, namespace: str, root: Optional[Path] = None) -> None:
        self.namespace = namespace
        self.root = root or Path(
            os.environ.get("REPLAY_CACHE_DIR", str(ROOT / "data/cache/replay"))
        )
        self.enabled = os.environ.get("REPLAY_CACHE_ENABLED", "true").lower() == "true"

    @classmethod
    def for_session(cls, db: Session) -> "RuntimeReplayCache":
        url = str(db.get_bind().url)
        namespace = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        return cls(namespace=namespace)

    def load(self, date: str, bbox: Optional[str], limit: int) -> Optional[ReplaySnapshotResponse]:
        if not self.enabled:
            return None
        path = self._path(date, bbox, limit)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return ReplaySnapshotResponse.model_validate(payload)
        except Exception as exc:
            logger.warning("Ignoring invalid replay cache %s: %s", path, exc)
            return None

    def store(
        self,
        date: str,
        bbox: Optional[str],
        limit: int,
        response: ReplaySnapshotResponse,
    ) -> None:
        if not self.enabled:
            return
        path = self._path(date, bbox, limit)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(response.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(path)
        except Exception as exc:
            logger.warning("Could not write replay cache %s: %s", path, exc)

    def _path(self, date: str, bbox: Optional[str], limit: int) -> Path:
        normalized_bbox = "" if bbox is None else ",".join(
            f"{float(value.strip()):.5f}" for value in bbox.split(",")
        )
        raw = f"{CACHE_SCHEMA_VERSION}|{self.namespace}|{date}|{normalized_bbox}|{limit}"
        key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.root / self.namespace / date / f"{key}.json"
