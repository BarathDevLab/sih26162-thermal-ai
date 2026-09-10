"""Tests for automatic stale-stack catch-up gating."""

from backend.app.services.stack_readiness import StackReadinessReport
from backend.app.services.startup_catchup import should_start_startup_catchup


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
