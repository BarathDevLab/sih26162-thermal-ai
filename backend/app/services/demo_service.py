"""Read and verify the deterministic, network-independent replay demo bundle."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from backend.app.schemas.demo import DemoScenario, DemoScenarioCollection, DemoStatus
from backend.app.schemas.replay import ReplaySnapshotResponse


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "backend/config/demo_scenarios.json"
DEFAULT_CACHE_ROOT = ROOT / "data/demo/replay"


def date_range(start: str, end: str) -> Iterable[str]:
    current = datetime.strptime(start, "%Y-%m-%d").date()
    final = datetime.strptime(end, "%Y-%m-%d").date()
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


class DemoService:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        cache_root: Optional[Path] = None,
    ) -> None:
        self.config_path = config_path or Path(
            os.environ.get("DEMO_SCENARIOS_PATH", str(DEFAULT_CONFIG))
        )
        self.cache_root = cache_root or Path(
            os.environ.get("DEMO_CACHE_ROOT", str(DEFAULT_CACHE_ROOT))
        )
        self.collection = DemoScenarioCollection.model_validate_json(
            self.config_path.read_text(encoding="utf-8")
        )
        self._validate_collection()

    def scenarios(self) -> DemoScenarioCollection:
        return self.collection

    def get_scenario(self, scenario_id: str) -> DemoScenario:
        for scenario in self.collection.scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        raise KeyError(scenario_id)

    def snapshot(self, scenario_id: str, snapshot_date: Optional[str] = None) -> ReplaySnapshotResponse:
        scenario = self.get_scenario(scenario_id)
        requested = snapshot_date or scenario.focal_date
        if requested not in set(date_range(scenario.start_date, scenario.end_date)):
            raise ValueError(
                f"Date {requested} is outside scenario range "
                f"{scenario.start_date}..{scenario.end_date}."
            )
        path = self.snapshot_path(scenario_id, requested)
        payload = path.read_bytes()
        self._verify_checksum(path, payload)
        response = ReplaySnapshotResponse.model_validate_json(payload)
        if response.as_of_date != requested:
            raise ValueError(f"Cached snapshot date mismatch in {path}")
        return response.model_copy(update={"cache_status": "DEMO_CACHE"})

    def status(self) -> DemoStatus:
        expected = []
        missing = []
        invalid = []
        cached_scenarios = 0
        for scenario in self.collection.scenarios:
            scenario_complete = True
            for snapshot_date in date_range(scenario.start_date, scenario.end_date):
                label = f"{scenario.scenario_id}/{snapshot_date}"
                expected.append(label)
                try:
                    self.snapshot(scenario.scenario_id, snapshot_date)
                except FileNotFoundError:
                    missing.append(label)
                    scenario_complete = False
                except Exception as exc:
                    invalid.append(f"{label}: {exc}")
                    scenario_complete = False
            if scenario_complete:
                cached_scenarios += 1
        return DemoStatus(
            status="READY" if not missing and not invalid else "INCOMPLETE",
            scenario_count=len(self.collection.scenarios),
            cached_scenario_count=cached_scenarios,
            expected_snapshot_count=len(expected),
            cached_snapshot_count=len(expected) - len(missing) - len(invalid),
            missing_snapshots=missing,
            invalid_snapshots=invalid,
            bundle_manifest_present=(self.cache_root / "manifest.json").is_file(),
        )

    def snapshot_path(self, scenario_id: str, snapshot_date: str) -> Path:
        return self.cache_root / scenario_id / f"{snapshot_date}.json"

    def _verify_checksum(self, path: Path, payload: bytes) -> None:
        manifest_path = self.cache_root / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("Demo bundle manifest is missing.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = path.relative_to(self.cache_root).as_posix()
        expected = manifest.get("files", {}).get(relative)
        if not expected:
            raise ValueError(f"Demo bundle checksum is missing for {relative}")
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ValueError(f"Demo bundle checksum mismatch for {relative}")

    def _validate_collection(self) -> None:
        seen = set()
        for scenario in self.collection.scenarios:
            if scenario.scenario_id in seen:
                raise ValueError(f"Duplicate demo scenario: {scenario.scenario_id}")
            seen.add(scenario.scenario_id)
            start = date.fromisoformat(scenario.start_date)
            focal = date.fromisoformat(scenario.focal_date)
            end = date.fromisoformat(scenario.end_date)
            if not start <= focal <= end:
                raise ValueError(f"Invalid date range for {scenario.scenario_id}")
            min_lon, min_lat, max_lon, max_lat = scenario.bbox
            if min_lon > max_lon or min_lat > max_lat:
                raise ValueError(f"Invalid bbox for {scenario.scenario_id}")
