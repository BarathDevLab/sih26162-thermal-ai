import math
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union

EARTH_RADIUS_M = 6371000.0

ORDERED_FEATURES = [
    'mean_frp', 'median_frp', 'max_frp', 'std_frp', 'frp_cv',
    'frp_p10', 'frp_p25', 'frp_p75', 'frp_p90', 'frp_iqr',
    'night_ratio',
    'detections', 'active_days', 'source_lifetime_days',
    'active_days_7', 'active_days_30', 'active_days_90', 'active_days_365',
    'mean_recurrence_gap_days', 'median_recurrence_gap_days',
    'detections_per_active_day',
    'spatial_median_m', 'spatial_p90_m', 'spatial_std_m',
    'tree_fraction', 'shrub_fraction', 'grass_fraction', 'crop_fraction',
    'built_fraction', 'bare_fraction', 'water_fraction', 'wetland_fraction',
    'mangrove_fraction'
]

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
                dt = date.today()
            dates.append(dt)

        # 1. Thermal features (T) - 11 features
        frp_arr = np.array(frp_vals, dtype=float)
        mean_frp = float(np.mean(frp_arr))
        median_frp = float(np.median(frp_arr))
        max_frp = float(np.max(frp_arr))
        std_frp = float(np.std(frp_arr)) if len(frp_arr) > 1 else 0.0
        frp_cv = float(std_frp / (mean_frp + 1e-6))
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
            mean_recurrence_gap_days = 0.0
            median_recurrence_gap_days = 0.0

        # 3. Spatial dispersion features (S) - 3 features
        lats = [float(d['latitude']) for d in detections if 'latitude' in d]
        lons = [float(d['longitude']) for d in detections if 'longitude' in d]
        
        c_lat = centroid_lat if centroid_lat is not None else (np.mean(lats) if lats else 0.0)
        c_lon = centroid_lon if centroid_lon is not None else (np.mean(lons) if lons else 0.0)

        if len(lats) > 1:
            distances = [haversine_m(lat, lon, c_lat, c_lon) for lat, lon in zip(lats, lons)]
            spatial_median_m = float(np.median(distances))
            spatial_p90_m = float(np.percentile(distances, 90))
            spatial_std_m = float(np.std(distances))
        else:
            spatial_median_m = 0.0
            spatial_p90_m = 0.0
            spatial_std_m = 0.0

        # 4. Land cover features (L) - 9 features
        lc = land_cover or {}
        tree_fraction = float(lc.get('tree_fraction', np.nan))
        shrub_fraction = float(lc.get('shrub_fraction', np.nan))
        grass_fraction = float(lc.get('grass_fraction', np.nan))
        crop_fraction = float(lc.get('crop_fraction', np.nan))
        built_fraction = float(lc.get('built_fraction', np.nan))
        bare_fraction = float(lc.get('bare_fraction', np.nan))
        water_fraction = float(lc.get('water_fraction', np.nan))
        wetland_fraction = float(lc.get('wetland_fraction', np.nan))
        mangrove_fraction = float(lc.get('mangrove_fraction', np.nan))

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
