import os
import pytest
import pandas as pd
from backend.app.engines.model_b import ModelBEngine

@pytest.fixture
def engine():
    return ModelBEngine()

def test_model_b_synthetic_scenarios(engine):
    # 1. New source: first seen 15d ago, active 5d ago, as of today
    r_new = engine.predict(['2025-05-01', '2025-05-10'], as_of_date='2025-05-15')
    assert r_new['state'] == 'NEW'

    # 2. Dormant source: last active 120d ago
    r_dorm = engine.predict(['2025-01-01', '2025-01-10'], as_of_date='2025-05-15')
    assert r_dorm['state'] == 'DORMANT'

    # 3. Reactivated source: returned after >=90d gap
    r_react = engine.predict(['2025-01-01', '2025-01-05', '2025-05-01'], as_of_date='2025-05-10')
    assert r_react['state'] == 'REACTIVATED'

def test_model_b_reproduce_frozen_2025_counts(engine):
    csv_path = 'data/bootstrap/MODEL_B_SOURCE_STATES_FINAL.csv'
    if not os.path.exists(csv_path):
        pytest.skip(f'{csv_path} not found')

    df_b = pd.read_csv(csv_path)
    pred_states = []
    
    for _, row in df_b.iterrows():
        res = engine.predict_from_stats(row.to_dict())
        pred_states.append(res['state'])
        
    df_b['engine_state'] = pred_states
    counts = df_b['engine_state'].value_counts().to_dict()

    # Verify exact reproduction of frozen counts
    assert counts.get('DORMANT', 0) == 61890
    assert counts.get('INTERMITTENT', 0) == 10399
    assert counts.get('REACTIVATED', 0) == 5047
    assert counts.get('NEW', 0) == 1551
    assert counts.get('PERSISTENT', 0) == 478
