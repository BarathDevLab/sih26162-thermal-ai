"""Lazy official Prithvi encoder plus the frozen Model A visual head."""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np

from backend.app.services.hls_service import HLSPatch


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "backend/models/prithvi/Prithvi_EO_V2_300M.pt"
CONFIG = ROOT / "backend/models/prithvi/config.json"
HEAD = ROOT / "backend/models/MODEL_A_PRITHVI_FINAL.joblib"
HEAD_CONFIG = ROOT / "backend/config/source/prithvi_final_config.json"
MANIFEST = ROOT / "backend/config/active_stack_manifest.json"
EXPECTED_ARCHITECTURE = "prithvi_eo_v2_300"
EXPECTED_EMBEDDING_DIM = 1024
HLS_REFLECTANCE_SCALE = 10_000.0


class PrithviUnavailable(RuntimeError):
    """Raised when genuine Prithvi inference cannot be executed."""


@dataclass(frozen=True)
class PrithviResult:
    probability: float
    embedding: np.ndarray
    model_revision: str


@dataclass(frozen=True)
class _PrithviContract:
    encoder_config: dict[str, Any]
    head: Any
    model_revision: str


class _PrithviRuntime:
    """One lazily materialized encoder per worker process."""

    def __init__(self, device: str, contract: _PrithviContract) -> None:
        try:
            import torch

            from backend.models.prithvi.prithvi_mae import PrithviViT
        except ImportError as exc:
            raise PrithviUnavailable(f"Prithvi runtime dependency is missing: {exc}") from exc

        config = contract.encoder_config
        model_keys = (
            "img_size",
            "num_frames",
            "patch_size",
            "in_chans",
            "embed_dim",
            "depth",
            "num_heads",
            "mlp_ratio",
            "coords_encoding",
            "coords_scale_learn",
        )
        model_config = {key: config[key] for key in model_keys}

        logger.info("Loading Prithvi-EO-2.0-300M encoder on %s (lazy first use)", device)
        try:
            # Meta construction avoids allocating a second 1.2 GB copy before
            # assigning tensors from the memory-mapped official checkpoint.
            with torch.device("meta"):
                model = PrithviViT(**model_config)
            state = torch.load(WEIGHTS, map_location="cpu", weights_only=True, mmap=True)
            if not isinstance(state, dict):
                raise TypeError("checkpoint does not contain a state dictionary")
            encoder_state = {
                key.removeprefix("encoder."): value
                for key, value in state.items()
                if key.startswith("encoder.")
            }
            if not encoder_state:
                raise ValueError("checkpoint contains no encoder weights")
            model.load_state_dict(encoder_state, strict=True, assign=True)
            del encoder_state, state
            model = model.to(device)
            model.requires_grad_(False)
            model.eval()
        except Exception as exc:
            raise PrithviUnavailable(f"Unable to load official Prithvi encoder: {exc}") from exc

        self.torch = torch
        self.model = model
        self.device = device

    def encode(self, input_data: np.ndarray) -> np.ndarray:
        torch = self.torch
        try:
            tensor = torch.from_numpy(np.ascontiguousarray(input_data)).to(self.device)
            with torch.inference_mode():
                features = self.model.forward_features(tensor)
                # The frozen linear-probe head consumes the final-layer CLS token.
                embedding = features[-1][:, 0, :]
            result = embedding[0].detach().float().cpu().numpy()
        except Exception as exc:
            raise PrithviUnavailable(f"Prithvi encoder inference failed: {exc}") from exc
        return np.asarray(result, dtype=np.float32)


_runtime: Optional[_PrithviRuntime] = None
_runtime_device: Optional[str] = None
_runtime_lock = threading.Lock()
_cpu_fallback_warned = False


class PrithviService:
    """Validate artifacts immediately and perform encoder inference lazily."""

    def __init__(self) -> None:
        missing = [str(path) for path in (WEIGHTS, CONFIG, HEAD, HEAD_CONFIG) if not path.is_file()]
        if missing:
            raise PrithviUnavailable(f"Required official Prithvi artifacts are missing: {missing}")
        self.contract = _load_contract()
        self.device = _resolve_device()
        self.execution_ready = True

    def score(self, patch: HLSPatch) -> PrithviResult:
        patch.validate()
        input_data = _prepare_prithvi_input(patch, self.contract.encoder_config)
        runtime = _get_runtime(self.device, self.contract)
        embedding = runtime.encode(input_data)
        if embedding.shape != (EXPECTED_EMBEDDING_DIM,) or not np.isfinite(embedding).all():
            raise PrithviUnavailable(
                f"Prithvi produced an invalid embedding with shape {embedding.shape}."
            )
        try:
            probabilities = self.contract.head.predict_proba(embedding.reshape(1, -1))
            probability = float(probabilities[0, 1])
        except Exception as exc:
            raise PrithviUnavailable(f"Frozen Prithvi classifier failed: {exc}") from exc
        if not np.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise PrithviUnavailable(f"Frozen Prithvi classifier returned {probability!r}.")
        return PrithviResult(
            probability=probability,
            embedding=embedding,
            model_revision=self.contract.model_revision,
        )


def _prepare_prithvi_input(patch: HLSPatch, config: dict[str, Any]) -> np.ndarray:
    """Create the frozen pilot tensor: B,C,T,H,W = 1,6,4,224,224."""

    bands = np.asarray(patch.bands, dtype=np.float32)
    mean = np.asarray(config["mean"], dtype=np.float32)[:, None, None]
    std = np.asarray(config["std"], dtype=np.float32)[:, None, None]
    if mean.shape != (6, 1, 1) or std.shape != (6, 1, 1) or np.any(std <= 0):
        raise PrithviUnavailable("Official Prithvi normalization statistics are invalid.")

    # HLSService stores physical reflectance. The official statistics are for
    # HLS integer units (scale factor 0.0001), so restore that scale first.
    normalized = (bands * HLS_REFLECTANCE_SCALE - mean) / std
    # HLSService masks invalid/cloud pixels to zero across every channel. The
    # frozen pilot mean-filled those pixels, which is zero after normalization.
    invalid = np.all(bands == 0.0, axis=0)
    normalized[:, invalid] = 0.0

    frame_count = int(config["num_frames"])
    if frame_count != 4:
        raise PrithviUnavailable(
            f"Frozen Prithvi pilot requires four repeated frames, got {frame_count}."
        )
    repeated = np.repeat(normalized[:, None, :, :], frame_count, axis=1)
    return np.ascontiguousarray(repeated[None, ...], dtype=np.float32)


@lru_cache(maxsize=1)
def _load_contract() -> _PrithviContract:
    try:
        import joblib

        encoder_blob = json.loads(CONFIG.read_text(encoding="utf-8"))
        policy_blob = json.loads(HEAD_CONFIG.read_text(encoding="utf-8"))
        head_blob = joblib.load(HEAD)
    except Exception as exc:
        raise PrithviUnavailable(f"Unable to read packaged Prithvi artifacts: {exc}") from exc

    if encoder_blob.get("architecture") != EXPECTED_ARCHITECTURE:
        raise PrithviUnavailable("Unexpected Prithvi encoder architecture.")
    if int(encoder_blob.get("num_features", -1)) != EXPECTED_EMBEDDING_DIM:
        raise PrithviUnavailable("Unexpected Prithvi encoder feature dimension.")
    config = encoder_blob.get("pretrained_cfg")
    if not isinstance(config, dict):
        raise PrithviUnavailable("Prithvi pretrained_cfg is missing.")
    expected = {
        "img_size": 224,
        "num_frames": 4,
        "in_chans": 6,
        "embed_dim": EXPECTED_EMBEDDING_DIM,
    }
    mismatches = {
        key: config.get(key) for key, value in expected.items() if config.get(key) != value
    }
    if mismatches:
        raise PrithviUnavailable(f"Prithvi encoder config violates the frozen contract: {mismatches}")

    if not isinstance(head_blob, dict) or "model" not in head_blob or "config" not in head_blob:
        raise PrithviUnavailable("Prithvi head artifact must contain model and config entries.")
    head = head_blob["model"]
    artifact_policy = head_blob["config"]
    if not isinstance(artifact_policy, dict) or not isinstance(policy_blob, dict):
        raise PrithviUnavailable("Prithvi rescue-policy config is invalid.")
    if int(getattr(head, "n_features_in_", -1)) != EXPECTED_EMBEDDING_DIM:
        raise PrithviUnavailable("Frozen Prithvi head does not accept 1024 features.")
    classes = np.asarray(getattr(head, "classes_", []))
    if classes.tolist() != [0, 1]:
        raise PrithviUnavailable(f"Unexpected Prithvi classifier classes: {classes.tolist()}")

    policy_fields = (
        "model",
        "embedding_dim",
        "threshold",
        "a_core_low",
        "a_core_core",
        "a_core_strong",
    )
    disagreements = {
        key: (artifact_policy.get(key), policy_blob.get(key))
        for key in policy_fields
        if artifact_policy.get(key) != policy_blob.get(key)
    }
    if disagreements:
        raise PrithviUnavailable(f"Prithvi head/config policy mismatch: {disagreements}")

    return _PrithviContract(
        encoder_config=config,
        head=head,
        model_revision=_model_revision(),
    )


def _resolve_device() -> str:
    global _cpu_fallback_warned
    try:
        import torch
    except ImportError as exc:
        raise PrithviUnavailable("torch is not installed.") from exc

    requested = os.environ.get("PRITHVI_DEVICE", "auto").strip().lower()
    if requested in ("", "auto"):
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cpu":
        return "cpu"
    if requested.startswith("cuda"):
        if torch.cuda.is_available():
            return requested
        allow_fallback = os.environ.get("PRITHVI_ALLOW_CPU_FALLBACK", "true").lower() == "true"
        if allow_fallback:
            if not _cpu_fallback_warned:
                logger.warning(
                    "PRITHVI_DEVICE=%s requested but CUDA is unavailable; using CPU. "
                    "First inference will be slow.",
                    requested,
                )
                _cpu_fallback_warned = True
            return "cpu"
        raise PrithviUnavailable(
            f"PRITHVI_DEVICE={requested} requested but this Torch build has no CUDA support."
        )
    raise PrithviUnavailable(f"Unsupported PRITHVI_DEVICE value: {requested!r}")


def _get_runtime(device: str, contract: _PrithviContract) -> _PrithviRuntime:
    global _runtime, _runtime_device
    with _runtime_lock:
        if _runtime is None or _runtime_device != device:
            _runtime = _PrithviRuntime(device, contract)
            _runtime_device = device
        return _runtime


def _model_revision() -> str:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        hashes = {
            item["repo_path"]: item["sha256"]
            for item in manifest.get("artifacts", [])
            if isinstance(item, dict) and "repo_path" in item and "sha256" in item
        }
        weights_hash = hashes[WEIGHTS.relative_to(ROOT).as_posix()]
        head_hash = hashes[HEAD.relative_to(ROOT).as_posix()]
    except Exception as exc:
        raise PrithviUnavailable(f"Prithvi artifact revisions are absent from the manifest: {exc}") from exc
    return f"Prithvi-EO-2.0-300M@{weights_hash[:12]}+head@{head_hash[:12]}"


def prithvi_readiness_issue() -> Optional[str]:
    try:
        service = PrithviService()
    except PrithviUnavailable as exc:
        return str(exc)
    if not service.execution_ready:
        return "Official Prithvi encoder/head execution is not ready."
    return None
