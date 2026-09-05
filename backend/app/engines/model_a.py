import os
import joblib
import pandas as pd
from typing import Dict, Any, Optional, Union

MODEL_PATH_DEFAULT = "backend/models/MODEL_A_FINAL.joblib"

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

        # Ensure compatibility across scikit-learn versions for unpickled SimpleImputer
        if hasattr(self.pipeline, 'steps'):
            for _, step in self.pipeline.steps:
                if hasattr(step, 'statistics_') and not hasattr(step, '_fill_dtype'):
                    step._fill_dtype = getattr(step.statistics_, 'dtype', None)

        # Frozen guarded thresholds
        thresholds = self.config.get('thresholds', {})
        self.thresh_low = float(thresholds.get('low', 0.405))
        self.thresh_core = float(thresholds.get('core', 0.885))
        self.thresh_strong = float(thresholds.get('strong', 0.975))
        self.thresh_prithvi_rescue = 0.965

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
            "core_probability": round(p_core, 4),
            "prithvi_used": prithvi_used,
            "prithvi_probability": round(float(prithvi_probability), 4) if prithvi_probability is not None else None,
            "thresholds": {
                "low": self.thresh_low,
                "core": self.thresh_core,
                "strong": self.thresh_strong,
                "prithvi_rescue": self.thresh_prithvi_rescue
            }
        }
