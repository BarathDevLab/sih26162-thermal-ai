# CLAUDE.md — SIH26162 implementation contract

You are implementing **SIH26162: AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources**.

This repository already has frozen research/model decisions. Your job is **implementation, packaging, regression verification, 2026 backfill, backend/API/database, and the OSIRIS-style web command center**. Do not silently retrain or redesign frozen logic.

## Source of truth

Read in this order before coding:

1. `docs/00_overview.md`
2. Relevant model/data doc: `01_data_and_ground_truth.md`, `02_model_a.md`, `03_model_b.md`, `04_model_c.md`
3. `docs/05_validation_claims.md`
4. `docs/06_decision_engine.md` (draft policy; not frozen yet)
5. `docs/07_firms_integration.md`
6. `docs/08_backend_and_db.md`
7. `docs/09_frontend.md`
8. `docs/10_deployment_ops.md`
9. `docs/11_testing_roadmap.md`
10. `docs/13_artifacts_env_contract.md`

Machine-readable values are under `backend/config/`. If prose and config disagree, stop and reconcile against `docs/99_full_validated_source.md`; do not guess.

## Current frozen architecture

- Source resolver: 750 m DBSCAN-derived physical sites, `min_samples=3`.
- Model A: XGBoost A-Core `T+R+S+L` + optional guarded Prithvi visual rescue.
- Model B: deterministic temporal-state engine, not a fitted ML estimator.
- Model C: V3 site-specific unsupervised statistical anomaly engine; Isolation Forest is ablation only.
- Decision engine: deterministic A+B+C policy **to implement and then freeze**.
- Frontend: presentation only; all FIRMS/Earthdata/model logic stays server-side.

## Mandatory implementation order

1. **P0 packaging gate:** verify required Drive/runtime artifacts exist, copy them into repository locations, generate SHA-256 checksums, and write active stack manifest.
2. Implement `feature_builder.py`, `model_a.py`, `model_b.py`, `model_c.py`, `source_resolver.py` plus golden regression tests.
3. Implement FIRMS client and 2026 backfill from `2026-01-01` through deployment date. Do not expose live mode on the stale 2025 B/C snapshot.
4. Implement and test the draft decision engine across A/B/C combinations; audit alert burden; only then freeze `decision_engine.json`.
5. Create PostGIS schema and bootstrap frozen sites/history/evidence/current status.
6. Implement FastAPI endpoints and SSE/WebSocket alert updates.
7. Build MapLibre/deck.gl OSIRIS-style UI.
8. Add scheduler, replay/demo hardening and asynchronous HLS/Prithvi queue.

## Non-negotiable do-not-do rules

- Do not change the 750 m source radius to 1000 m for web implementation.
- Do not random-split hotspot rows for Model A evaluation.
- Do not use FIRMS type 2 as industrial truth or type 3 as automatic offshore flare truth.
- Do not add OSM distance features back into A-Core without a new non-circular experiment.
- Do not add nighttime-light features back into production A-Core based on intuition.
- Do not let missing OSM/GEM context force `NONINDUSTRIAL`.
- Do not let Prithvi veto A-Core `>= 0.885`.
- Do not replace `UNKNOWN` with a confident class for UI cleanliness.
- Do not call Model B an ML model; it is a deterministic temporal-state engine.
- Do not calculate Model B recent windows using source `last_seen` semantics; use live/replay `as_of_date`.
- Do not let Model C use future observations in a historical baseline.
- Do not treat long recurrence gaps as Model C anomaly; dormancy/reactivation belongs to Model B.
- Do not call `INSUFFICIENT_HISTORY` normal.
- Do not report Model C supervised accuracy until independent anomaly ground truth exists.
- Do not use Isolation Forest to override V3 production Model C.
- Do not rerun full DBSCAN on each ingestion cycle or web request.
- Do not call FIRMS/Earthdata directly from the browser.
- Do not expose MAP_KEY/Earthdata credentials to frontend code.
- Do not mix NOAA-21 into A-Core feature streams until sensor harmonization has a regression audit.
- Do not start live mode from the frozen 2025 temporal snapshot; backfill 2026 first.

## Exact frozen values

Never duplicate thresholds manually when code can load `backend/config/frozen_thresholds.json`. Exact Model A feature order is in `backend/config/model_a_features.json`. Model B and C executable specifications are in `backend/config/model_b.json` and `backend/config/model_c.json`.

## Runtime behavior that must remain true

- New FIRMS detections are normalized/deduplicated server-side and incrementally assigned to stable sites.
- Ambiguous live source matches are audited; frozen sites are not silently merged.
- A-Core returns immediately; HLS/Prithvi is asynchronous/optional for A-Core uncertainty only.
- Model B is refreshed for touched sites immediately and globally at least daily because time can change state without a new detection.
- Model C scores the current site-day against **prior completed active days only**.
- `NO_RECENT_EVENT` is presentation status, not a Model C anomaly class.
- Alerts are deduplicated/escalated using a stable fingerprint rather than emitted repeatedly for the same site-day.
- Historical replay must use the replay date as the temporal cutoff and must not leak current/final state backward in time.

## Completion gates

Do not mark a phase complete without the regression checks in `docs/11_testing_roadmap.md`. In particular, the original 2025 cutoff must reproduce Model B frozen counts and Model C V3 distributions, and known Model A golden rows must reproduce stored probabilities/decisions within tolerance.

## Claims discipline

Follow `docs/05_validation_claims.md`. The system is decision support, not life-safety-grade fire confirmation. Model C has sensitivity/chronological validation but no independent event-level industrial-fire ground truth yet.
