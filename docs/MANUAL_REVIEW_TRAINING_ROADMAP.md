# UNKNOWN Review and Training-Evidence Roadmap

Status: active implementation roadmap. This does not change the frozen production Model A policy.

## Objective

Turn selected UNKNOWN-source analyst adjudications into traceable future research labels without allowing manual actions, alert acknowledgement, or Prithvi output to silently mutate production inference.

## Non-negotiable boundaries

- Model A output and provenance remain immutable machine evidence.
- Alert acknowledgement is not a classification label.
- Prithvi rescue is model evidence, not independent human truth.
- `REMAIN_UNKNOWN` and reviewer conflicts are preserved and excluded from supervised binary training.
- No online or automatic retraining is permitted.
- A replacement model requires offline training, site/time/country-separated validation, regression gates, a new artifact checksum, and an approved stack version.

## Delivery phases

### R1 — Auditable review foundation

- Append-only `site_reviews` ledger.
- UNKNOWN review queue API.
- Live-only site Review tab.
- Determination, confidence, reason codes, evidence attestations, notes, operator and timestamp.
- Exact Model A output and 33-feature snapshot captured at review time.
- No mutation endpoints for existing review records.

### R2 — Independent verification

- First completed review becomes `AWAITING_VERIFICATION`.
- Matching review from a different operator becomes `VERIFIED`.
- Disagreement becomes `CONFLICT` and remains excluded from training.
- Only two-reviewer, high-confidence, evidence-backed binary determinations are export-eligible.

### R3 — Review operations

- Dedicated queue panel with assignment, SLA/age, filters and country routing.
- Replace self-entered prototype operator IDs with authenticated workspace identities and review roles.
- Blind second review so the verifier does not see the first determination before submitting.
- Supervisor conflict resolution as another append-only event.
- Reviewer calibration metrics and periodic spot checks.

### R4 — Dataset release

- Export only consensus-verified rows with their captured 33-feature snapshots.
- Produce a versioned manifest containing review IDs, evidence references, feature schema, country coverage and label counts.
- Freeze site-level, chronological and country holdouts before experimentation.
- Detect duplicate/nearby sites across folds to prevent spatial leakage.

### R5 — Model experimentation

- Train candidates offline; never update the runtime model from the review API.
- Compare against the frozen A-Core on original golden rows and untouched natural-distribution holdouts.
- Report per-country performance, calibration, class balance and UNKNOWN coverage.
- Treat reviewed samples as human evidence with measured inter-reviewer agreement—not unquestioned ground truth.

### R6 — Governed deployment

- Approve a new versioned model only after regression, geographic and alert-burden review.
- Package artifact/config checksums and update the active stack manifest.
- Preserve rollback to the current frozen model and retain every review/dataset/model lineage link.

## Current implementation commands

Apply all database migrations through the standard runtime setup. For an existing PostgreSQL database, apply the new migration directly:

```powershell
psql --dbname=sih26162 --set=ON_ERROR_STOP=1 --file=backend/migrations/002_site_reviews.sql
```

Export eligible research rows without retraining:

```powershell
.\.venv\Scripts\python.exe backend/scripts/export_review_training_data.py
```

The default output is a timestamped Parquet file under `data/exports/`.
