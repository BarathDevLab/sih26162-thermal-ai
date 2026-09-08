"""Fail-closed official Prithvi encoder/head service boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from backend.app.services.hls_service import HLSPatch


ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "backend/models/prithvi/Prithvi_EO_V2_300M.pt"
CONFIG = ROOT / "backend/models/prithvi/config.json"
HEAD = ROOT / "backend/models/MODEL_A_PRITHVI_FINAL.joblib"
HEAD_CONFIG = ROOT / "backend/config/source/prithvi_final_config.json"


class PrithviUnavailable(RuntimeError):
    pass


@dataclass
class PrithviResult:
    probability: float
    embedding: np.ndarray
    model_revision: str


class PrithviService:
    def __init__(self) -> None:
        missing = [str(path) for path in (WEIGHTS, CONFIG, HEAD, HEAD_CONFIG) if not path.is_file()]
        if missing:
            raise PrithviUnavailable(f"Required official Prithvi artifacts are missing: {missing}")
        # This service remains deliberately unavailable until the packaged head's
        # preprocessing and encoder-output contract can be verified end to end.
        self.execution_ready = False

    def score(self, patch: HLSPatch) -> PrithviResult:
        patch.validate()
        # Loading the official encoder/head is intentionally blocked until the
        # frozen head is packaged. Returning a heuristic probability is forbidden.
        raise PrithviUnavailable(
            "Official Prithvi head execution is not activated for this artifact set."
        )


def prithvi_readiness_issue() -> Optional[str]:
    try:
        service = PrithviService()
    except PrithviUnavailable as exc:
        return str(exc)
    if not service.execution_ready:
        return "Official Prithvi encoder/head execution has not passed its pilot regression gate."
    return None
