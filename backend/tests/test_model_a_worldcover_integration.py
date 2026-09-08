from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import FirmsDetection, SourceSite
from backend.app.db.session import Base
from backend.app.services.feature_builder import ORDERED_FEATURES
from backend.app.services.model_a_service import ModelAService


class StubModelAEngine:
    feature_names = ORDERED_FEATURES
    thresh_low = 0.405
    thresh_core = 0.885

    def predict(self, frame, prithvi_probability=None):
        assert frame["water_fraction"].iat[0] == 1.0
        return {
            "class": "NONINDUSTRIAL",
            "decision": "NONINDUSTRIAL",
            "core_probability": 0.1,
            "prithvi_probability": prithvi_probability,
            "thresholds": {"low": 0.405, "core": 0.885, "strong": 0.975},
        }


class StubWorldCover:
    def __init__(self):
        self.calls = 0

    def get_fractions(self, latitude, longitude):
        self.calls += 1
        return {
            "tree_fraction": 0.0,
            "shrub_fraction": 0.0,
            "grass_fraction": 0.0,
            "crop_fraction": 0.0,
            "built_fraction": 0.0,
            "bare_fraction": 0.0,
            "water_fraction": 1.0,
            "wetland_fraction": 0.0,
            "mangrove_fraction": 0.0,
        }


def test_model_a_hydrates_and_persists_worldcover_once():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    worldcover = StubWorldCover()
    service = ModelAService(
        engine=StubModelAEngine(), worldcover_service=worldcover
    )
    try:
        db.add(SourceSite(site_id="SITE_WC", latitude=22.1, longitude=72.5))
        db.add(FirmsDetection(
            detection_id="DET_WC",
            source_sensor="NOAA20_VIIRS",
            satellite="20",
            instrument="VIIRS",
            latitude=22.1,
            longitude=72.5,
            acq_date=date(2026, 1, 1),
            acq_time="0830",
            frp=10.0,
            confidence="nominal",
            daynight="D",
            version="2.0NRT",
            source_site_id="SITE_WC",
        ))
        db.commit()

        first = service.score_site(db, "SITE_WC")
        second = service.score_site(db, "SITE_WC")

        assert first["class"] == "NONINDUSTRIAL"
        assert second["class"] == "NONINDUSTRIAL"
        assert worldcover.calls == 1
        assert db.query(SourceSite).filter_by(site_id="SITE_WC").one().land_cover[
            "water_fraction"
        ] == 1.0
    finally:
        db.close()


def test_model_a_sensor_family_excludes_noaa21():
    accepted = ModelAService._accepted_sensor_sources("VIIRS_NOAA20_NRT")
    assert "NOAA20_VIIRS" in accepted
    assert "VIIRS_NOAA20_SP" in accepted
    assert "VIIRS_NOAA20_NRT" in accepted
    assert "VIIRS_NOAA21_NRT" not in accepted
