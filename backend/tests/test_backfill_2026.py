"""
Tests for 2026 Backfill Orchestrator
Verifies 5-day window partitioning, bootstrap data loading, and end-to-end backfill execution in dry-run mode.
"""

import os
import tempfile
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import FirmsDetection, SiteModelB, SourceSite
from backend.app.db.session import Base
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.firms_client import DEFAULT_PRIMARY_SOURCE, FirmsClient
from backend.app.services.model_a_service import LAND_COVER_FEATURES


def test_generate_5day_windows():
    windows = BackfillOrchestrator.generate_5day_windows("2026-01-01", "2026-01-12")
    # Day count: 12 days total -> 5 + 5 + 2
    assert len(windows) == 3
    assert windows[0] == ("2026-01-01", 5)
    assert windows[1] == ("2026-01-06", 5)
    assert windows[2] == ("2026-01-11", 2)


def test_generate_5day_windows_single_day():
    windows = BackfillOrchestrator.generate_5day_windows("2026-03-01", "2026-03-01")
    assert len(windows) == 1
    assert windows[0] == ("2026-03-01", 1)


def test_available_windows_bridge_noaa20_sp_to_nrt():
    availability = [
        {"data_id": "VIIRS_NOAA20_SP", "min_date": "2018-04-01", "max_date": "2026-05-31"},
        {"data_id": "VIIRS_NOAA20_NRT", "min_date": "2026-06-01", "max_date": "2026-09-08"},
    ]
    windows = BackfillOrchestrator.build_available_source_windows(
        date(2026, 1, 1), date(2026, 9, 8), "VIIRS_NOAA20_NRT", availability
    )

    assert windows[0] == ("VIIRS_NOAA20_SP", "2026-01-01", 5)
    assert ("VIIRS_NOAA20_SP", "2026-05-31", 1) in windows
    assert ("VIIRS_NOAA20_NRT", "2026-06-01", 5) in windows
    assert windows[-1] == ("VIIRS_NOAA20_NRT", "2026-09-04", 5)
    assert sum(window[2] for window in windows) == 251


def test_available_windows_reject_gap_in_source_family():
    availability = [
        {"data_id": "VIIRS_NOAA20_SP", "min_date": "2018-04-01", "max_date": "2026-05-30"},
        {"data_id": "VIIRS_NOAA20_NRT", "min_date": "2026-06-01", "max_date": "2026-09-08"},
    ]
    with pytest.raises(RuntimeError, match="2026-05-31"):
        BackfillOrchestrator.build_available_source_windows(
            date(2026, 1, 1), date(2026, 9, 8), "VIIRS_NOAA20_NRT", availability
        )


def test_backfill_dry_run_offline():
    client = FirmsClient(offline_mode=True)
    progress_events = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        orchestrator = BackfillOrchestrator(
            firms_client=client,
            output_dir=tmp_dir
        )
        # Run a 2-day backfill in dry_run mode
        res = orchestrator.run_backfill(
            start_date="2026-01-01",
            end_date="2026-01-02",
            dry_run=True,
            progress_callback=progress_events.append,
        )

        assert res["start_date"] == "2026-01-01"
        assert res["end_date"] == "2026-01-02"
        assert res["total_windows"] == 1
        assert res["dry_run"] is True
        assert progress_events[-1]["phase"] == "SYNCING_FIRMS"
        assert progress_events[-1]["completed_windows"] == 1
        assert progress_events[-1]["total_windows"] == 1


def test_incremental_stack_refresh_only_scores_sites_active_after_snapshot():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    class FakeModelA:
        def __init__(self):
            self.scored = []

        def score_site(self, db, site_id, **kwargs):
            self.scored.append(site_id)
            return {"decision": "UNKNOWN"}

    class FakeModelCReplay:
        def __init__(self):
            self.scored = []

        def replay_site(self, db, site_id, cutoff=None):
            self.scored.append(site_id)
            return {
                "event_date": cutoff,
                "latest": {"status": "INSUFFICIENT_HISTORY"},
            }

    class FakePipeline:
        def __init__(self):
            self.model_a = FakeModelA()
            self.model_c_replay = FakeModelCReplay()

        def _evaluate_alert(self, *args, **kwargs):
            return 0

    pipeline = FakePipeline()
    orchestrator = BackfillOrchestrator(pipeline=pipeline)
    land_cover = {name: 0.0 for name in LAND_COVER_FEATURES}
    try:
        for site_id, activity_date in (
            ("SITE_OLD", date(2026, 1, 10)),
            ("SITE_NEW", date(2026, 9, 9)),
        ):
            db.add(SourceSite(
                site_id=site_id,
                latitude=20.0,
                longitude=75.0,
                land_cover=land_cover,
            ))
            db.add(FirmsDetection(
                detection_id=f"DET_{site_id}",
                source_sensor=DEFAULT_PRIMARY_SOURCE,
                satellite="20",
                instrument="VIIRS",
                latitude=20.0,
                longitude=75.0,
                acq_date=activity_date,
                acq_time="0830",
                frp=10.0,
                confidence="nominal",
                daynight="D",
                version="2.0",
                source_site_id=site_id,
            ))
            db.add(SiteModelB(
                site_id=site_id,
                state="DORMANT",
                confidence="HIGH",
                model_version="test",
            ))
        db.commit()

        unavailable = orchestrator._refresh_2026_stack(
            db,
            refresh_start=date(2026, 9, 9),
            target=date(2026, 9, 10),
            source=DEFAULT_PRIMARY_SOURCE,
        )

        assert unavailable == {}
        assert pipeline.model_a.scored == ["SITE_NEW"]
        assert pipeline.model_c_replay.scored == ["SITE_NEW"]
    finally:
        db.close()
