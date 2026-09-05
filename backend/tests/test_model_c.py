import os
import pytest
import pandas as pd
from backend.app.engines.model_c import ModelCEngine

@pytest.fixture
def engine():
    return ModelCEngine()

def test_model_c_cold_start(engine):
    # Less than 5 days history
    prior = [
        {'acq_date': '2025-01-01', 'detections': 1, 'max_frp': 10.0, 'mean_frp': 10.0},
        {'acq_date': '2025-01-02', 'detections': 2, 'max_frp': 12.0, 'mean_frp': 11.0}
    ]
    curr = {'acq_date': '2025-01-10', 'detections': 3, 'max_frp': 15.0, 'mean_frp': 14.0}
    
    res = engine.score(prior, curr)
    assert res['status'] == 'INSUFFICIENT_HISTORY'
    assert res['history_ok'] is False
    assert res['c_score'] is None

def test_model_c_replay_accuracy(engine):
    parquet_path = 'data/bootstrap/MODEL_C_EVENT_REPLAY_V3.parquet'
    if not os.path.exists(parquet_path):
        pytest.skip(f'{parquet_path} not found')

    df_c = pd.read_parquet(parquet_path)
    site1 = df_c[df_c['site_id'] == 'INDIA_SITE_0000001'].sort_values('acq_date')

    # Row 5 was the first scoreable event
    prior = site1.iloc[:5].to_dict('records')
    curr = site1.iloc[5].to_dict()

    res = engine.score(prior, curr)
    assert res['history_ok'] is True
    assert res['status'] == curr['model_c_level']
    assert abs(res['c_score'] - curr['c_score']) < 1e-4
