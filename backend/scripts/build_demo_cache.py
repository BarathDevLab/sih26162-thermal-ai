"""Build and verify deterministic historical replay snapshots for offline demos."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.demo_service import DemoService, date_range
from backend.app.services.replay_service import build_replay_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", action="append", help="Build only this scenario ID")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    service = DemoService()
    selected = [
        scenario
        for scenario in service.collection.scenarios
        if not args.scenario or scenario.scenario_id in set(args.scenario)
    ]
    if args.scenario and len(selected) != len(set(args.scenario)):
        known = {scenario.scenario_id for scenario in selected}
        missing = sorted(set(args.scenario) - known)
        print(json.dumps({"status": "ERROR", "unknown_scenarios": missing}, indent=2))
        return 2

    if not args.verify_only:
        files = _existing_manifest_files(service)
        with SessionLocal() as db:
            for scenario in selected:
                bbox = ",".join(str(value) for value in scenario.bbox)
                focal_response = None
                for snapshot_date in date_range(scenario.start_date, scenario.end_date):
                    response = build_replay_snapshot(
                        db,
                        cutoff=date.fromisoformat(snapshot_date),
                        bbox=bbox,
                        limit=scenario.limit,
                    ).model_copy(update={"cache_status": "DEMO_CACHE"})
                    target = service.snapshot_path(scenario.scenario_id, snapshot_date)
                    payload = json.dumps(
                        response.model_dump(mode="json"),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    _atomic_write(target, payload)
                    relative = target.relative_to(service.cache_root).as_posix()
                    files[relative] = hashlib.sha256(payload).hexdigest()
                    if snapshot_date == scenario.focal_date:
                        focal_response = response
                if focal_response is None:
                    raise RuntimeError(f"No focal response built for {scenario.scenario_id}")
                _verify_expected(scenario, focal_response)

        config_payload = service.config_path.read_bytes()
        manifest = {
            "schema_version": "1.0",
            "model_stack_version": service.collection.model_stack_version,
            "scenario_config_sha256": hashlib.sha256(config_payload).hexdigest(),
            "files": dict(sorted(files.items())),
        }
        _atomic_write(
            service.cache_root / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

    verification = _verify_bundle(service)
    print(json.dumps(verification, indent=2, sort_keys=True))
    return 0 if verification["status"] == "READY" else 2


def _verify_bundle(service: DemoService) -> dict:
    status = service.status()
    focal_checks = {}
    if status.status == "READY":
        for scenario in service.collection.scenarios:
            try:
                _verify_expected(scenario, service.snapshot(scenario.scenario_id))
                focal_checks[scenario.scenario_id] = "PASS"
            except Exception as exc:
                focal_checks[scenario.scenario_id] = f"FAIL: {exc}"
    all_focal_pass = focal_checks and all(value == "PASS" for value in focal_checks.values())
    payload = status.model_dump(mode="json")
    payload["focal_checks"] = focal_checks
    payload["status"] = "READY" if status.status == "READY" and all_focal_pass else "INCOMPLETE"
    return payload


def _verify_expected(scenario, response) -> None:
    feature = next(
        (
            item
            for item in response.features
            if item.properties.site_id == scenario.site_id
        ),
        None,
    )
    if feature is None:
        raise ValueError(f"Focal site {scenario.site_id} is missing")
    properties = feature.properties.model_dump(mode="json")
    mismatches = {
        key: {"expected": expected, "actual": properties.get(key)}
        for key, expected in scenario.expected.items()
        if properties.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"Focal expectation mismatch: {mismatches}")


def _existing_manifest_files(service: DemoService) -> dict:
    path = service.cache_root / "manifest.json"
    if not path.is_file():
        return {}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("files", {}))
    except Exception:
        return {}


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
