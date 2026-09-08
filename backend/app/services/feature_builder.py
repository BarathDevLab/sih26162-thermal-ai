import math
import json
from pathlib import Path

import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union

# Exact radius used by the frozen Model A training notebook.
EARTH_RADIUS_M = 6371008.8

_FEATURE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "model_a_features.json"
with _FEATURE_CONFIG_PATH.open("r", encoding="utf-8") as _feature_config_file:
    _FEATURE_CONFIG = json.load(_feature_config_file)
ORDERED_FEATURES = list(_FEATURE_CONFIG["ordered_features"])
FEATURE_VERSION = str(_FEATURE_CONFIG.get("schema_version", "unknown"))

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    return EARTH_RADIUS_M * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

class FeatureBuilder:
    def __init__(self):
        self.feature_names = list(ORDERED_FEATURES)

    def build_features_from_detections(
        self,
        detections: List[Dict[str, Any]],
        centroid_lat: Optional[float] = None,
        centroid_lon: Optional[float] = None,
        land_cover: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        if not detections:
            raise ValueError("Detections list cannot be empty.")

        # Parse FRP and brightness
        frp_vals = [float(d.get('frp', 0.0)) for d in detections]
        daynights = [str(d.get('daynight', 'D')).upper() for d in detections]
        
        # Parse acquisition dates
        dates = []
        for d in detections:
            dt_val = d.get('acq_date')
            if isinstance(dt_val, str):
                dt = datetime.strptime(dt_val[:10], '%Y-%m-%d').date()
            elif isinstance(dt_val, datetime):
                dt = dt_val.date()
            elif isinstance(dt_val, date):
                dt = dt_val
            else:
                raise ValueError("Every detection must contain a valid acq_date.")
            dates.append(dt)

        # 1. Thermal features (T) - 11 features
        frp_arr = np.array(frp_vals, dtype=float)
        mean_frp = float(np.mean(frp_arr))
        median_frp = float(np.median(frp_arr))
        max_frp = float(np.max(frp_arr))
        # The frozen notebook used pandas Series.std(), whose default is the
        # sample standard deviation (ddof=1). A one-row source therefore has
        # a missing value which is handled by the serialized model's imputer.
        std_frp = float(np.std(frp_arr, ddof=1)) if len(frp_arr) > 1 else np.nan
        frp_cv = float(std_frp / max(mean_frp, 1e-6))
        frp_p10 = float(np.percentile(frp_arr, 10))
        frp_p25 = float(np.percentile(frp_arr, 25))
        frp_p75 = float(np.percentile(frp_arr, 75))
        frp_p90 = float(np.percentile(frp_arr, 90))
        frp_iqr = float(frp_p75 - frp_p25)
        night_ratio = float(sum(1 for dn in daynights if dn == 'N') / len(daynights))

        # 2. Recurrence / persistence features (R) - 10 features
        unique_dates = sorted(list(set(dates)))
        detections_count = len(detections)
        active_days = len(unique_dates)
        first_date = unique_dates[0]
        last_date = unique_dates[-1]
        source_lifetime_days = max(1, (last_date - first_date).days + 1)
        detections_per_active_day = float(detections_count / active_days)

        # Active days within trailing windows from last detection date
        def active_in_last_days(n_days: int) -> int:
            return sum(1 for d in unique_dates if (last_date - d).days < n_days)

        active_days_7 = active_in_last_days(7)
        active_days_30 = active_in_last_days(30)
        active_days_90 = active_in_last_days(90)
        active_days_365 = active_in_last_days(365)

        if len(unique_dates) > 1:
            gaps = [(unique_dates[i] - unique_dates[i-1]).days for i in range(1, len(unique_dates))]
            mean_recurrence_gap_days = float(np.mean(gaps))
            median_recurrence_gap_days = float(np.median(gaps))
        else:
            mean_recurrence_gap_days = np.nan
            median_recurrence_gap_days = np.nan

        # 3. Spatial dispersion features (S) - 3 features
        coordinate_pairs = [
            (float(d['latitude']), float(d['longitude']))
            for d in detections
            if d.get('latitude') is not None and d.get('longitude') is not None
        ]
        lats = [pair[0] for pair in coordinate_pairs]
        lons = [pair[1] for pair in coordinate_pairs]
        
        c_lat = centroid_lat if centroid_lat is not None else (np.median(lats) if lats else 0.0)
        c_lon = centroid_lon if centroid_lon is not None else (np.median(lons) if lons else 0.0)

        if lats:
            # Match the training notebook's local tangent-plane approximation.
            dx = EARTH_RADIUS_M * np.cos(np.radians(c_lat)) * np.radians(np.asarray(lons) - c_lon)
            dy = EARTH_RADIUS_M * np.radians(np.asarray(lats) - c_lat)
            distances = np.sqrt(dx ** 2 + dy ** 2)
            spatial_median_m = float(np.median(distances))
            spatial_p90_m = float(np.quantile(distances, 0.90))
            spatial_std_m = float(np.std(distances))
        else:
            spatial_median_m = 0.0
            spatial_p90_m = 0.0
            spatial_std_m = 0.0

        # 4. Land cover features (L) - 9 features
        lc = land_cover or {}
        def land_cover_value(name: str) -> float:
            value = lc.get(name)
            return np.nan if value is None else float(value)

        tree_fraction = land_cover_value('tree_fraction')
        shrub_fraction = land_cover_value('shrub_fraction')
        grass_fraction = land_cover_value('grass_fraction')
        crop_fraction = land_cover_value('crop_fraction')
        built_fraction = land_cover_value('built_fraction')
        bare_fraction = land_cover_value('bare_fraction')
        water_fraction = land_cover_value('water_fraction')
        wetland_fraction = land_cover_value('wetland_fraction')
        mangrove_fraction = land_cover_value('mangrove_fraction')

        row_dict = {
            'mean_frp': mean_frp,
            'median_frp': median_frp,
            'max_frp': max_frp,
            'std_frp': std_frp,
            'frp_cv': frp_cv,
            'frp_p10': frp_p10,
            'frp_p25': frp_p25,
            'frp_p75': frp_p75,
            'frp_p90': frp_p90,
            'frp_iqr': frp_iqr,
            'night_ratio': night_ratio,
            'detections': detections_count,
            'active_days': active_days,
            'source_lifetime_days': source_lifetime_days,
            'active_days_7': active_days_7,
            'active_days_30': active_days_30,
            'active_days_90': active_days_90,
            'active_days_365': active_days_365,
            'mean_recurrence_gap_days': mean_recurrence_gap_days,
            'median_recurrence_gap_days': median_recurrence_gap_days,
            'detections_per_active_day': detections_per_active_day,
            'spatial_median_m': spatial_median_m,
            'spatial_p90_m': spatial_p90_m,
            'spatial_std_m': spatial_std_m,
            'tree_fraction': tree_fraction,
            'shrub_fraction': shrub_fraction,
            'grass_fraction': grass_fraction,
            'crop_fraction': crop_fraction,
            'built_fraction': built_fraction,
            'bare_fraction': bare_fraction,
            'water_fraction': water_fraction,
            'wetland_fraction': wetland_fraction,
            'mangrove_fraction': mangrove_fraction
        }

        # Return DataFrame in exact canonical order
        return pd.DataFrame([row_dict], columns=ORDERED_FEATURES)
