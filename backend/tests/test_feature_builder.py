import pytest
import numpy as np
from backend.app.services.feature_builder import FeatureBuilder, ORDERED_FEATURES

def test_feature_builder_columns():
    builder = FeatureBuilder()
    assert len(builder.feature_names) == 33
    assert builder.feature_names == ORDERED_FEATURES

def test_feature_builder_extraction():
    builder = FeatureBuilder()
    dets = [
        {'frp': 15.0, 'daynight': 'D', 'acq_date': '2025-01-01', 'latitude': 20.0, 'longitude': 78.0},
        {'frp': 30.0, 'daynight': 'N', 'acq_date': '2025-01-05', 'latitude': 20.001, 'longitude': 78.001},
        {'frp': 45.0, 'daynight': 'N', 'acq_date': '2025-01-15', 'latitude': 20.002, 'longitude': 78.002}
    ]

    df = builder.build_features_from_detections(dets, centroid_lat=20.0, centroid_lon=78.0)
    assert df.shape == (1, 33)
    assert list(df.columns) == ORDERED_FEATURES

    # Check thermal values
    assert df['mean_frp'].iloc[0] == 30.0
    assert df['min_frp' if 'min_frp' in df else 'max_frp'].iloc[0] == 45.0
    assert df['night_ratio'].iloc[0] == pytest.approx(2/3)

    # Check recurrence values
    assert df['detections'].iloc[0] == 3
    assert df['active_days'].iloc[0] == 3
    assert df['source_lifetime_days'].iloc[0] == 15
    assert df['mean_recurrence_gap_days'].iloc[0] == pytest.approx(7.0)

    # Land cover NaN when not provided
    assert np.isnan(df['tree_fraction'].iloc[0])
