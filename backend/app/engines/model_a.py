import json
import os
from pathlib import Path

import joblib
import pandas as pd
from typing import Dict, Any, Optional, Union

MODEL_PATH_DEFAULT = "backend/models/MODEL_A_FINAL.joblib"
_ROOT = Path(__file__).resolve().parents[3]
FEATURE_CONFIG_PATH = _ROOT / "backend" / "config" / "model_a_features.json"
THRESHOLD_CONFIG_PATH = _ROOT / "backend" / "config" / "frozen_thresholds.json"

class ModelAEngine:
    def __init__(self, model_path: str = MODEL_PATH_DEFAULT):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model A artifact not found at {model_path}")
            
        data = joblib.load(model_path)
        if isinstance(data, dict):
            self.pipeline = data.get('model')
            self.config = data.get('config', {})
        else:
            self.pipeline = data
            self.config = {}

        if self.pipeline is None or not hasattr(self.pipeline, "predict_proba"):
            raise ValueError("MODEL_A_FINAL.joblib does not contain a predict_proba pipeline.")

        with FEATURE_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            feature_config = json.load(fh)
        self.feature_names = list(feature_config["ordered_features"])
        self.feature_version = str(feature_config.get("schema_version", "unknown"))

        artifact_features = getattr(self.pipeline, "feature_names_in_", None)
        if artifact_features is not None and list(artifact_features) != self.feature_names:
            raise ValueError("Model A artifact feature order does not match model_a_features.json.")

        # Ensure compatibility across scikit-learn versions for unpickled SimpleImputer
        if hasattr(self.pipeline, 'steps'):
            for _, step in self.pipeline.steps:
                if hasattr(step, 'statistics_') and not hasattr(step, '_fill_dtype'):
                    step._fill_dtype = getattr(step.statistics_, 'dtype', None)

        # Frozen guarded thresholds
        with THRESHOLD_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            frozen_thresholds = json.load(fh)["model_a"]
        artifact_thresholds = self.config.get('thresholds', {})
        self.thresh_low = float(frozen_thresholds["low"])
        self.thresh_core = float(frozen_thresholds["core"])
        self.thresh_strong = float(frozen_thresholds["strong"])
        self.thresh_prithvi_rescue = float(frozen_thresholds["prithvi_strong_rescue"])
        for name, expected in (
            ("low", self.thresh_low),
            ("core", self.thresh_core),
            ("strong", self.thresh_strong),
        ):
            if name in artifact_thresholds and abs(float(artifact_thresholds[name]) - expected) > 1e-9:
                raise ValueError(f"Model A artifact threshold '{name}' disagrees with frozen config.")

    def predict(
        self,
        features_df: pd.DataFrame,
        prithvi_probability: Optional[float] = None
    ) -> Dict[str, Any]:
        if features_df is None or len(features_df) == 0:
            raise ValueError("Input features DataFrame is empty.")

        # Ensure single row inference format
        if len(features_df) > 1:
            input_row = features_df.iloc[[0]]
        else:
            input_row = features_df

        actual_features = list(input_row.columns)
        if actual_features != self.feature_names:
            raise ValueError(
                f"Model A feature order mismatch: expected {self.feature_names}, got {actual_features}"
            )

        probs = self.pipeline.predict_proba(input_row)[0]
        # Class 1 is INDUSTRIAL, Class 0 is NONINDUSTRIAL
        p_core = float(probs[1])

        # Guarded Decision Logic
        if p_core >= self.thresh_strong:
            decision = "INDUSTRIAL_CORE_STRONG"
            predicted_class = "INDUSTRIAL"
            prithvi_used = False
        elif p_core >= self.thresh_core:
            decision = "INDUSTRIAL_CORE_POSITIVE"
            predicted_class = "INDUSTRIAL"
            prithvi_used = False
        elif p_core >= self.thresh_low:
            # Uncertainty band [0.405, 0.885)
            if prithvi_probability is not None and prithvi_probability >= self.thresh_prithvi_rescue:
                decision = "INDUSTRIAL_PRITHVI_RESCUE"
                predicted_class = "INDUSTRIAL"
                prithvi_used = True
            else:
                decision = "UNKNOWN"
                predicted_class = "UNKNOWN"
                prithvi_used = (prithvi_probability is not None)
        else:
            decision = "NONINDUSTRIAL"
            predicted_class = "NONINDUSTRIAL"
            prithvi_used = False

        return {
            "class": predicted_class,
            "decision": decision,
            "core_probability": p_core,
            "prithvi_used": prithvi_used,
            "prithvi_probability": float(prithvi_probability) if prithvi_probability is not None else None,
            "thresholds": {
                "low": self.thresh_low,
                "core": self.thresh_core,
                "strong": self.thresh_strong,
                "prithvi_rescue": self.thresh_prithvi_rescue
            }
        }
