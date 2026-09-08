import os
import math
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path

MODEL_C_PATH_DEFAULT = "backend/models/MODEL_C_V3_FROZEN.joblib"

class ModelCEngine:
    """
    Model C V3: Site-Specific Unsupervised Statistical Anomaly Engine.
    Learns baseline from prior active days strictly before current day.
    Evaluates 4 anomaly groups: intensity, density, recurrence burst, and change.
    Appends two-stage midrank empirical percentile calibration.
    """

    def __init__(self, model_path: str = MODEL_C_PATH_DEFAULT):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model C calibration artifact not found at {model_path}")

        data = joblib.load(model_path)
        required_keys = {"config", "group_reference", "final_reference"}
        if not isinstance(data, dict) or not required_keys.issubset(data):
            raise ValueError("Model C artifact is missing calibration/config payloads.")
        self.config = data["config"]
        self.group_reference = data["group_reference"]
        required_groups = ("intensity_raw", "density_raw", "recurrence_raw", "change_raw")
        if not isinstance(self.group_reference, dict):
            raise ValueError("Model C group calibration payload must be a mapping.")
        for group in required_groups:
            if group not in self.group_reference:
                raise ValueError(f"Model C artifact is missing '{group}' calibration.")
            values = np.asarray(self.group_reference[group], dtype=float)
            if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
                raise ValueError(f"Model C '{group}' calibration must be finite and non-empty.")
            if np.any(values[1:] < values[:-1]):
                raise ValueError(f"Model C '{group}' calibration must be sorted.")
            self.group_reference[group] = values
        self.final_reference = np.asarray(data["final_reference"], dtype=float)
        if (
            self.final_reference.ndim != 1
            or self.final_reference.size == 0
            or not np.isfinite(self.final_reference).all()
            or np.any(self.final_reference[1:] < self.final_reference[:-1])
        ):
            raise ValueError("Model C final calibration must be finite, non-empty, and sorted.")

        root = Path(__file__).resolve().parents[3]
        with (root / "backend/config/frozen_thresholds.json").open("r", encoding="utf-8") as fh:
            frozen = json.load(fh)["model_c"]
        self.min_active_history = int(frozen["min_active_history"])
        self.min_span_days = int(frozen["min_span_days"])
        self.min_gap_history = int(frozen["min_gap_history"])
        self.ewma_alpha = float(frozen["ewma_alpha"])
        self.cusum_k = float(frozen["cusum_k"])
        self.cusum_cap = float(frozen["cusum_cap"])
        self.change_reset_gap = float(frozen["change_reset_gap_days"])
        self.z_cap = float(frozen["z_cap"])
        severity = frozen["severity"]
        self.elevated_threshold = float(severity["elevated"]["gte"])
        self.anomalous_threshold = float(severity["anomalous"]["gte"])
        self.critical_threshold = float(severity["critical"]["gte"])
        artifact_values = {
            "min_active_history": self.min_active_history,
            "min_span_days": self.min_span_days,
            "min_gap_history": self.min_gap_history,
            "ewma_alpha": self.ewma_alpha,
            "cusum_k": self.cusum_k,
            "cusum_cap": self.cusum_cap,
            "z_cap": self.z_cap,
        }
        for key, expected in artifact_values.items():
            if key in self.config and float(self.config[key]) != float(expected):
                raise ValueError(f"Model C artifact parameter '{key}' disagrees with frozen config.")

    def _midrank_percentile(self, reference_array: np.ndarray, value: float) -> float:
        n = len(reference_array)
        left = int(np.searchsorted(reference_array, value, side="left"))
        right = int(np.searchsorted(reference_array, value, side="right"))
        return (left + right) / (2.0 * n)

    def _robust_location_scale(self, values: np.ndarray) -> Tuple[float, float]:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        scale = 1.4826 * mad
        if scale < 1e-4:
            q75, q25 = np.percentile(values, [75, 25])
            iqr = q75 - q25
            scale = iqr / 1.349
        scale = max(scale, 0.05 * abs(median), 1e-3)
        return median, scale

    def score(
        self,
        prior_history: List[Dict[str, Any]],
        current_day: Dict[str, Any],
        prev_ewma: float = 0.0,
        prev_cusum: float = 0.0
    ) -> Dict[str, Any]:
        """
        Scores a single active day against prior completed active days.
        """
        # Parse current day info
        curr_detections = int(current_day.get("detections", 1))
        curr_mean_frp = float(current_day.get("mean_frp", 0.0))
        curr_max_frp = float(current_day.get("max_frp", 0.0))
        curr_date = current_day.get("acq_date")
        if isinstance(curr_date, str):
            curr_date = datetime.strptime(curr_date[:10], "%Y-%m-%d").date()
        elif isinstance(curr_date, datetime):
            curr_date = curr_date.date()

        history_active_days = len(prior_history)

        # Check cold-start requirements
        if history_active_days < self.min_active_history:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "c_score": None,
                "reason": f"Active days ({history_active_days}) < required ({self.min_active_history})",
                "history_active_days": history_active_days,
                "history_ok": False
            }

        # Parse prior dates and verify history span
        prior_dates = []
        for p in prior_history:
            d_val = p.get("acq_date")
            if isinstance(d_val, str):
                d = datetime.strptime(d_val[:10], "%Y-%m-%d").date()
            elif isinstance(d_val, datetime):
                d = d_val.date()
            else:
                d = d_val
            prior_dates.append(d)

        prior_dates.sort()
        first_date = prior_dates[0]
        last_prior_date = prior_dates[-1]
        history_span_days = (curr_date - first_date).days
        gap_days = float((curr_date - last_prior_date).days)

        if history_span_days < self.min_span_days:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "c_score": None,
                "reason": f"History span ({history_span_days}d) < required ({self.min_span_days}d)",
                "history_active_days": history_active_days,
                "history_span_days": history_span_days,
                "history_ok": False
            }

        # 1. Intensity Baseline (max_frp and mean_frp)
        prior_max_frps = np.array([float(p.get("max_frp", 0.0)) for p in prior_history], dtype=float)
        prior_mean_frps = np.array([float(p.get("mean_frp", 0.0)) for p in prior_history], dtype=float)

        base_max, scale_max = self._robust_location_scale(prior_max_frps)
        base_mean, scale_mean = self._robust_location_scale(prior_mean_frps)

        z_max_frp = max(0.0, min(self.z_cap, (curr_max_frp - base_max) / scale_max))
        z_mean_frp = max(0.0, min(self.z_cap, (curr_mean_frp - base_mean) / scale_mean))
        intensity_raw = max(z_max_frp, z_mean_frp)

        # 2. Density Baseline (log1p(detections))
        prior_log_dets = np.array([math.log1p(float(p.get("detections", 1))) for p in prior_history], dtype=float)
        base_log_det, scale_log_det = self._robust_location_scale(prior_log_dets)
        curr_log_det = math.log1p(curr_detections)
        density_raw = max(0.0, min(self.z_cap, (curr_log_det - base_log_det) / scale_log_det))

        # 3. Recurrence Burst Baseline (unexpectedly short return gap)
        prior_gaps = [(prior_dates[i] - prior_dates[i-1]).days for i in range(1, len(prior_dates))]
        if len(prior_gaps) >= self.min_gap_history:
            gaps_arr = np.array(prior_gaps, dtype=float)
            med_gap, scale_gap = self._robust_location_scale(gaps_arr)
            recurrence_raw = max(0.0, min(self.z_cap, (med_gap - gap_days) / scale_gap))
        else:
            recurrence_raw = 0.0

        # 4. Change Signal (EWMA and Bounded CUSUM)
        input_signal = max(intensity_raw, density_raw)
        if gap_days > self.change_reset_gap:
            ewma = self.ewma_alpha * input_signal
            cusum = max(0.0, min(self.cusum_cap, input_signal - self.cusum_k))
        else:
            ewma = self.ewma_alpha * input_signal + (1.0 - self.ewma_alpha) * prev_ewma
            cusum = max(0.0, min(self.cusum_cap, prev_cusum + input_signal - self.cusum_k))

        change_raw = max(ewma, cusum)

        # Calibrate groups to midrank percentiles
        pct_intensity = self._midrank_percentile(self.group_reference["intensity_raw"], intensity_raw)
        pct_density = self._midrank_percentile(self.group_reference["density_raw"], density_raw)
        pct_recurrence = self._midrank_percentile(self.group_reference["recurrence_raw"], recurrence_raw)
        pct_change = self._midrank_percentile(self.group_reference["change_raw"], change_raw)

        group_pcts = [
            ("intensity", pct_intensity),
            ("density", pct_density),
            ("recurrence_burst", pct_recurrence),
            ("change", pct_change)
        ]
        # Sort descending by percentile
        group_pcts.sort(key=lambda x: x[1], reverse=True)

        # Top-two composite average
        c_raw = (group_pcts[0][1] + group_pcts[1][1]) / 2.0

        # Final calibrated c_score
        c_score = self._midrank_percentile(self.final_reference, c_raw)

        # Map to severity status
        if c_score >= self.critical_threshold:
            status = "CRITICAL"
        elif c_score >= self.anomalous_threshold:
            status = "ANOMALOUS"
        elif c_score >= self.elevated_threshold:
            status = "ELEVATED"
        else:
            status = "NORMAL"

        anomaly_drivers = [name for name, pct in group_pcts if pct >= 0.95]
        if not anomaly_drivers:
            anomaly_drivers = [group_pcts[0][0]]

        return {
            "status": status,
            "c_score": round(c_score, 6),
            "c_raw": round(c_raw, 6),
            "group_scores": {
                "intensity": round(pct_intensity, 6),
                "density": round(pct_density, 6),
                "recurrence_burst": round(pct_recurrence, 6),
                "change": round(pct_change, 6)
            },
            "raw_signals": {
                "intensity_raw": round(intensity_raw, 6),
                "density_raw": round(density_raw, 6),
                "recurrence_raw": round(recurrence_raw, 6),
                "change_raw": round(change_raw, 6),
                "ewma_score": round(ewma, 6),
                "cusum_score": round(cusum, 6)
            },
            "drivers": anomaly_drivers,
            "history_active_days": history_active_days,
            "history_span_days": history_span_days,
            "gap_days": gap_days,
            "history_ok": True
        }
