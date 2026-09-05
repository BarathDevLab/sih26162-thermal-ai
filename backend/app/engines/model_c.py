import os
import math
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union, Tuple

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
        self.config = data["config"]
        self.group_reference = data["group_reference"]
        self.final_reference = data["final_reference"]

        # Parameters
        self.min_active_history = int(self.config.get("min_active_history", 5))
        self.min_span_days = int(self.config.get("min_span_days", 30))
        self.min_gap_history = int(self.config.get("min_gap_history", 3))
        self.ewma_alpha = float(self.config.get("ewma_alpha", 0.35))
        self.cusum_k = float(self.config.get("cusum_k", 2.0))
        self.cusum_cap = float(self.config.get("cusum_cap", 50.0))
        self.change_reset_gap = float(self.config.get("change_reset_gap", 30))
        self.z_cap = float(self.config.get("z_cap", 20.0))

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
        if c_score >= 0.999:
            status = "CRITICAL"
        elif c_score >= 0.990:
            status = "ANOMALOUS"
        elif c_score >= 0.950:
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
