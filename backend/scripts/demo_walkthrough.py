"""Verify the offline bundle and print the deterministic presenter walkthrough."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.demo_service import DemoService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        help="Optionally verify a running API, e.g. http://127.0.0.1:8000/api/v1",
    )
    args = parser.parse_args()

    service = DemoService()
    status = service.status()
    if status.status != "READY":
        print(json.dumps(status.model_dump(mode="json"), indent=2))
        print("Run: python -m backend.scripts.build_demo_cache")
        return 2

    if args.base_url:
        remote_status = _get_json(f"{args.base_url.rstrip('/')}/demo/status")
        if remote_status.get("status") != "READY":
            print(json.dumps(remote_status, indent=2))
            return 2

    print(service.collection.disclaimer)
    print(f"Offline bundle: {status.cached_snapshot_count} verified daily snapshots")
    for index, scenario in enumerate(service.collection.scenarios, start=1):
        snapshot = service.snapshot(scenario.scenario_id)
        if args.base_url:
            remote = _get_json(
                f"{args.base_url.rstrip('/')}/demo/scenarios/"
                f"{scenario.scenario_id}/snapshot?date={scenario.focal_date}"
            )
            if remote.get("cache_status") != "DEMO_CACHE":
                raise RuntimeError(f"API did not serve demo cache for {scenario.scenario_id}")
        focal = next(
            feature.properties
            for feature in snapshot.features
            if feature.properties.site_id == scenario.site_id
        )
        print(f"\n{index}. {scenario.title}")
        print(f"   Range: {scenario.start_date} to {scenario.end_date}; focal {scenario.focal_date}")
        print(f"   Site: {scenario.site_id}")
        print(
            f"   Expected focal state: A={focal.a_class}, B={focal.b_state}, "
            f"C={focal.c_status}, alert={focal.alert_type or 'NONE'}"
        )
        for line in scenario.talk_track:
            print(f"   - {line}")
    return 0


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


if __name__ == "__main__":
    raise SystemExit(main())
