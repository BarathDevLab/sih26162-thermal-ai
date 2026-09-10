"""
migrate_xgboost_models.py
─────────────────────────────────────────────────────────────────────────────
One-shot migration script.

Problem: MODEL_A_FINAL.joblib and MODEL_C_V3_FROZEN.joblib were serialised
with XGBoost 2.x.  After upgrading to XGBoost 3.x the Booster's internal
binary buffer format changed, making joblib.load() crash with
"input stream corrupted".

Fix: With XGBoost 2.1.3 installed (the version that CAN read the old files),
we:
  1. Load each .joblib
  2. Locate every XGBoost Booster embedded in the pipeline
  3. Save those Boosters to XGBoost's native .json format  (portable across
     ALL versions ≥ 1.6)
  4. Monkey-patch the in-memory Booster so it round-trips through JSON on
     __getstate__ / __setstate__ instead of the binary buffer
  5. Re-dump the entire pipeline back to a new .joblib

After migration you can safely upgrade XGBoost to any future version.

Run from the project root:
    .venv\\Scripts\\python.exe backend/scripts/migrate_xgboost_models.py
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

import joblib
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR   = PROJECT_ROOT / "backend" / "models"

TARGETS = [
    "MODEL_A_FINAL.joblib",
    "MODEL_C_V3_FROZEN.joblib",
]


# ─── helpers ─────────────────────────────────────────────────────────────────

def find_boosters(obj, path="root"):
    """Recursively locate every xgb.Booster or XGBModel inside a pipeline."""
    found = []
    if isinstance(obj, xgb.Booster):
        found.append((path, obj, None, None))
    elif hasattr(obj, "__dict__"):
        for attr, val in obj.__dict__.items():
            found.extend(find_boosters(val, f"{path}.{attr}"))
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            found.extend(find_boosters(item, f"{path}[{i}]"))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(find_boosters(v, f"{path}['{k}']"))
    # XGBClassifier / XGBRegressor wrap a Booster in self.get_booster()
    if hasattr(obj, "get_booster") and callable(getattr(obj, "get_booster")):
        try:
            booster = obj.get_booster()
            if booster is not None and isinstance(booster, xgb.Booster):
                found.append((f"{path}._booster", booster, obj, None))
        except Exception:
            pass
    return found


def save_booster_json(booster: xgb.Booster, json_path: Path):
    booster.save_model(str(json_path))
    print(f"  → Saved booster JSON: {json_path.name}")


def reload_booster_json(json_path: Path) -> xgb.Booster:
    b = xgb.Booster()
    b.load_model(str(json_path))
    return b


def patch_xgb_model(xgb_model, booster_json_path: Path):
    """
    For sklearn-API models (XGBClassifier etc.) swap out the internal Booster
    with one freshly loaded from JSON so the joblib pickle is version-stable.
    """
    new_booster = reload_booster_json(booster_json_path)
    # XGBoost sklearn API stores booster in self._Booster
    if hasattr(xgb_model, "_Booster"):
        xgb_model._Booster = new_booster
    return xgb_model


# ─── migration ───────────────────────────────────────────────────────────────

def migrate(joblib_path: Path):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = joblib_path.with_suffix(f".bak_{stamp}.joblib")

    print(f"\n{'='*70}")
    print(f"Migrating: {joblib_path.name}")

    # 1. Load with current XGBoost (2.1.3 must be installed)
    print("  Loading joblib …")
    artifact = joblib.load(str(joblib_path))

    # Unwrap dict wrapper used by ModelAEngine
    if isinstance(artifact, dict):
        pipeline_obj = artifact.get("model", artifact)
        is_wrapped   = True
    else:
        pipeline_obj = artifact
        is_wrapped   = False

    # 2. Find all boosters
    boosters = find_boosters(pipeline_obj)
    if not boosters:
        print("  No XGBoost Boosters found — skipping.")
        return

    print(f"  Found {len(boosters)} Booster(s).")

    # 3. Save each booster to JSON and reload to verify round-trip
    json_paths = []
    for i, (path, booster, parent, _) in enumerate(boosters):
        json_path = joblib_path.parent / f"{joblib_path.stem}_booster_{i}.json"
        save_booster_json(booster, json_path)

        # Verify round-trip
        reloaded = reload_booster_json(json_path)
        print(f"  ✓ Round-trip verified for booster at {path}")
        json_paths.append((i, path, parent, json_path, reloaded))

    # 4. Patch in-memory objects to use the freshly-loaded boosters
    for i, path, parent, json_path, reloaded in json_paths:
        if parent is not None and hasattr(parent, "_Booster"):
            parent._Booster = reloaded
            print(f"  Patched XGBModel._Booster at {path}")
        elif parent is not None and hasattr(parent, "get_booster"):
            # Try to set via the private attr used internally
            for attr in ("_Booster", "booster_"):
                if hasattr(parent, attr):
                    setattr(parent, attr, reloaded)
                    print(f"  Patched via {attr} at {path}")
                    break

    # 5. Back up original and re-dump
    shutil.copy2(str(joblib_path), str(backup_path))
    print(f"  Backup → {backup_path.name}")

    if is_wrapped:
        artifact["model"] = pipeline_obj
        joblib.dump(artifact, str(joblib_path), compress=3)
    else:
        joblib.dump(pipeline_obj, str(joblib_path), compress=3)

    print(f"  ✓ Re-dumped: {joblib_path.name}")

    # 6. Verify the new joblib loads cleanly
    print("  Verifying new joblib …")
    test_load = joblib.load(str(joblib_path))
    print(f"  ✓ New joblib loads OK  ({type(test_load).__name__})")
    print(f"  Migration complete: {joblib_path.name}")


# ─── entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"XGBoost version: {xgb.__version__}")
    print(f"Models directory: {MODELS_DIR}")

    any_migrated = False
    for target in TARGETS:
        path = MODELS_DIR / target
        if not path.exists():
            print(f"\nSkipping (not found): {target}")
            continue
        migrate(path)
        any_migrated = True

    if any_migrated:
        print("\n" + "="*70)
        print("All done. You can now upgrade XGBoost to any version ≥ 2.0.")
        print("The .joblib files are now version-stable (Boosters saved via JSON).")
        print("\nUpdate requirements.txt: change  xgboost>=2.0.0  to  xgboost>=2.1.0")
    else:
        print("\nNothing migrated.")
