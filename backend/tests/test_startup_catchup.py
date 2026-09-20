"""Tests for automatic stale-stack catch-up gating."""

from datetime import datetime, timedelta, timezone

from backend.app.services.stack_readiness import StackReadinessReport
from backend.app.services.startup_catchup import should_start_startup_catchup
from backend.app.services import startup_catchup


def test_stale_stack_with_firms_key_starts_automatic_catchup(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    monkeypatch.delenv("AUTO_STARTUP_CATCHUP", raising=False)

    assert should_start_startup_catchup(
        StackReadinessReport(status="STALE_BACKFILL", can_start_live=False)
    )


def test_automatic_catchup_requires_stale_status_and_credentials(monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    stale = StackReadinessReport(status="STALE_BACKFILL", can_start_live=False)
    ready = StackReadinessReport(status="READY", can_start_live=True)

    assert not should_start_startup_catchup(stale)
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    assert not should_start_startup_catchup(ready)


def test_automatic_catchup_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    monkeypatch.setenv("AUTO_STARTUP_CATCHUP", "false")

    assert not should_start_startup_catchup(
        StackReadinessReport(status="STALE_BACKFILL", can_start_live=False)
    )


def test_startup_catchup_exposes_mission_progress(monkeypatch):
    monkeypatch.setattr(startup_catchup, "_status", {
        "status": "RUNNING",
        "running": True,
    })

    startup_catchup._update_catchup_progress({
        "phase": "SYNCING_FIRMS",
        "progress_percent": 42,
        "completed_windows": 4,
        "total_windows": 9,
        "current_window_start": "2026-09-05",
        "current_window_end": "2026-09-09",
    })

    status = startup_catchup.get_startup_catchup_status()
    assert status["phase"] == "SYNCING_FIRMS"
    assert status["progress_percent"] == 42
    assert status["completed_windows"] == 4
    assert status["total_windows"] == 9
    assert status["updated_at"] is not None


def test_startup_catchup_exposes_timing_and_activity(monkeypatch):
    started_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    monkeypatch.setattr(startup_catchup, "_status", {
        "status": "RUNNING",
        "running": True,
        "phase": "SYNCING_FIRMS",
        "progress_percent": 20,
        "phase_progress_percent": 10,
        "started_at": started_at,
        "ended_at": None,
        "activity_log": [],
    })

    startup_catchup._update_catchup_progress({
        "phase": "SYNCING_FIRMS",
        "progress_percent": 25,
        "phase_progress_percent": 20,
        "detail": "Ingested FIRMS window 2026-09-01 through 2026-09-05.",
    })

    status = startup_catchup.get_startup_catchup_status()
    assert status["elapsed_seconds"] >= 59
    assert status["estimated_remaining_seconds"] is not None
    assert status["estimated_remaining_seconds"] > 0
    assert status["progress_rate_percent_per_minute"] is not None
    assert status["activity_log"][-1]["phase"] == "SYNCING_FIRMS"
    assert "Ingested FIRMS window" in status["activity_log"][-1]["message"]
