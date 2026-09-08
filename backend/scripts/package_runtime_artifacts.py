"""Copy authoritative artifacts into place and atomically write hashes/active manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.feature_validation import feature_validation_issue
from backend.app.services.stack_readiness import REQUIRED_FILES


MANIFEST_PATH = ROOT / "backend/config/active_stack_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, help="Root of recovered authoritative artifacts")
    parser.add_argument("--replace", action="store_true", help="Replace already present repo artifacts")
    args = parser.parse_args()

    if args.artifact_root:
        copy_from_artifact_root(args.artifact_root.resolve(), replace=args.replace)

    package_inputs = [path for path in REQUIRED_FILES if path != "backend/config/active_stack_manifest.json"]
    missing = [relative for relative in package_inputs if not (ROOT / relative).is_file()]
    if missing:
        print(json.dumps({"status": "INCOMPLETE", "missing": missing}, indent=2))
        return 2

    hashes = {relative: sha256(ROOT / relative) for relative in package_inputs}
    optional = [
        "backend/models/MODEL_A_PRITHVI_FINAL.joblib",
        "backend/models/prithvi/Prithvi_EO_V2_300M.pt",
        "backend/models/prithvi/config.json",
        "backend/models/prithvi/prithvi_mae.py",
        "backend/config/source/prithvi_final_config.json",
    ]
    for relative in optional:
        if (ROOT / relative).is_file():
            hashes[relative] = sha256(ROOT / relative)

    checksum_text = "".join(f"{digest}  {relative}\n" for relative, digest in sorted(hashes.items()))
    atomic_write(ROOT / "SHA256SUMS.txt", checksum_text)
    validation_issue = feature_validation_issue()
    manifest = {
        "schema_version": "1.0",
        "model_stack_version": "2026-09-04-r1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_BOOTSTRAP" if validation_issue is None else "FEATURE_VALIDATION_REQUIRED",
        "feature_validation": validation_issue or "PASS",
        "artifacts": [
            {"repo_path": relative, "sha256": digest, "required": relative in package_inputs}
            for relative, digest in sorted(hashes.items())
        ],
    }
    atomic_write(MANIFEST_PATH, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if validation_issue is None else 2


def copy_from_artifact_root(artifact_root: Path, replace: bool) -> None:
    source_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
    candidates = {
        item["repo_path"]: item["drive_path"]
        for item in source_manifest.get("artifacts", [])
    }
    for relative in REQUIRED_FILES:
        if relative == "backend/config/active_stack_manifest.json":
            continue
        destination = ROOT / relative
        if destination.exists() and not replace:
            continue
        possible = [
            artifact_root / candidates.get(relative, relative),
            artifact_root / relative,
            artifact_root / Path(relative).name,
        ]
        source = next((path for path in possible if path.is_file()), None)
        if source is None:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
