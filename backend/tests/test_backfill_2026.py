"""
Tests for 2026 Backfill Orchestrator
Verifies 5-day window partitioning, bootstrap data loading, and end-to-end backfill execution in dry-run mode.
"""

import os
import tempfile
import pytest
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.firms_client import FirmsClient


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


def test_backfill_dry_run_offline():
    client = FirmsClient(offline_mode=True)
    with tempfile.TemporaryDirectory() as tmp_dir:
        orchestrator = BackfillOrchestrator(
            firms_client=client,
            output_dir=tmp_dir
        )
        # Run a 2-day backfill in dry_run mode
        res = orchestrator.run_backfill(
            start_date="2026-01-01",
            end_date="2026-01-02",
            dry_run=True
        )

        assert res["start_date"] == "2026-01-01"
        assert res["end_date"] == "2026-01-02"
        assert res["total_windows"] == 1
        assert res["dry_run"] is True
