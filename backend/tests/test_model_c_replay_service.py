from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import SiteDailyActivity, SiteDailyInference, SourceSite
from backend.app.db.session import Base
from backend.app.services.model_c_replay_service import ModelCReplayService


class StubModelC:
    def score(self, history, current, prev_ewma=0.0, prev_cusum=0.0):
        return {
            "status": "INSUFFICIENT_HISTORY",
            "history_ok": False,
            "c_score": None,
            "c_raw": None,
            "group_scores": {},
            "evidence_99": 0,
            "drivers": [],
            "raw_signals": {},
        }


class StubModelB:
    def predict(self, active_dates, as_of_date):
        return {"state": "NEW"}


def test_replay_loads_existing_daily_inferences_once():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    site_id = "SITE_REPLAY_BATCHED"
    db.add(SourceSite(site_id=site_id, latitude=20.0, longitude=75.0))
    for day in range(1, 4):
        db.add(SiteDailyActivity(
            site_id=site_id,
            acq_date=date(2026, 1, day),
            detections=day,
            mean_frp=float(day),
            max_frp=float(day),
        ))
    db.add(SiteDailyInference(
        site_id=site_id,
        acq_date=date(2026, 1, 1),
        model_c_status="OLD",
        model_c_version="old",
    ))
    db.commit()

    inference_selects = []

    @event.listens_for(engine, "before_cursor_execute")
    def record_inference_select(conn, cursor, statement, parameters, context, executemany):
        normalized = statement.lower()
        if normalized.lstrip().startswith("select") and "site_daily_inference" in normalized:
            inference_selects.append(statement)

    try:
        service = ModelCReplayService(model_c=StubModelC(), model_b=StubModelB())
        result = service.replay_site(db, site_id, cutoff=date(2026, 1, 3))
        db.commit()
        assert result["replayed_days"] == 3
        assert len(inference_selects) == 1
        assert db.query(SiteDailyInference).filter_by(site_id=site_id).count() == 3
    finally:
        event.remove(engine, "before_cursor_execute", record_inference_select)
        db.close()
