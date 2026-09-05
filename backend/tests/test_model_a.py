import pytest
import pandas as pd
from backend.app.engines.model_a import ModelAEngine
from backend.app.services.feature_builder import ORDERED_FEATURES

@pytest.fixture
def engine():
    return ModelAEngine()

def test_model_a_thresholds(engine):
    assert engine.thresh_low == 0.405
    assert engine.thresh_core == pytest.approx(0.885, abs=1e-4)
    assert engine.thresh_strong == 0.975

def test_model_a_guarded_rescue(engine):
    # Simulated dataframe
    df = pd.DataFrame([{f: 1.0 for f in ORDERED_FEATURES}])
    
    # 1. Base prediction without Prithvi
    res = engine.predict(df)
    assert res['class'] in ['INDUSTRIAL', 'NONINDUSTRIAL', 'UNKNOWN']
    assert 0.0 <= res['core_probability'] <= 1.0

    # 2. Uncertainty band with Prithvi rescue
    # If core prob is uncertain, Prithvi >= 0.965 rescues
    # We can test guarded logic paths directly
    engine.thresh_low = 0.0
    engine.thresh_core = 1.0
    # Now any p_core will be uncertain [0.0, 1.0)
    
    res_no_prithvi = engine.predict(df)
    assert res_no_prithvi['class'] == 'UNKNOWN'
    assert res_no_prithvi['decision'] == 'UNKNOWN'

    res_rescued = engine.predict(df, prithvi_probability=0.98)
    assert res_rescued['class'] == 'INDUSTRIAL'
    assert res_rescued['decision'] == 'INDUSTRIAL_PRITHVI_RESCUE'
    assert res_rescued['prithvi_used'] is True

    res_not_rescued = engine.predict(df, prithvi_probability=0.85)
    assert res_not_rescued['class'] == 'UNKNOWN'
    assert res_not_rescued['decision'] == 'UNKNOWN'
