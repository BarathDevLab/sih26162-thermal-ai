# SIH26162 Project Phase Tracking & Task List

This living document tracks progress across all implementation phases defined in [docs/11_testing_roadmap.md](file:///c:/project/sih26162-thermal-ai/docs/11_testing_roadmap.md) and [CLAUDE.md](file:///c:/project/sih26162-thermal-ai/CLAUDE.md).

---

## Overall Status Summary

```
Phase 0: Freeze Packaging & Workspace Bootstrap  ──▶ [COMPLETED ✅]
Phase 1: Backend Intelligence Engines           ──▶ [COMPLETED ✅]
Phase 2: Live FIRMS Client & 2026 Backfill      ──▶ [COMPLETED ✅]
Phase 3: Decision & Alert Engine                ──▶ [COMPLETED ✅]
Phase 4: PostgreSQL / PostGIS Database Layer    ──▶ [READY TO START 📍]
Phase 5: Normalized FastAPI Endpoints           ──▶ [PENDING ⏳]
Phase 6: OSIRIS Web Command Center (Frontend)   ──▶ [PENDING ⏳]
Phase 7: Live Scheduling & Async Queues         ──▶ [PENDING ⏳]
Phase 8: Demo Replay & Hardening                ──▶ [PENDING ⏳]
```

---

## Detailed Phase Breakdown

### Phase 0: Freeze Packaging & Workspace Bootstrap
**Status:** **COMPLETED ✅**

- [x] **Repository Scaffold:** Established clean, modular layout (`backend/app/`, `backend/tests/`, `frontend/src/`).
- [x] **Package Cleanliness:** Replaced `.gitkeep` clutter with standard Python `__init__.py` modules.
- [x] **Dependencies:** Updated `backend/requirements.txt` with GIS (`shapely`, `pyproj`), ML (`xgboost`, `scikit-learn`), foundation models (`torch`, `timm`, `einops`), and data loaders (`pyarrow`).
- [x] **Model A-Core Ingestion:** Placed `backend/models/MODEL_A_FINAL.joblib`.
- [x] **Model C V3 Ingestion:** Placed `backend/models/MODEL_C_V3_FROZEN.joblib` (calibration dictionary).
- [x] **Prithvi Foundation Model:** Downloaded `Prithvi_EO_V2_300M.pt`, `config.json`, and `prithvi_mae.py` into `backend/models/prithvi/`.
- [x] **Checksum Integrity:** Generated SHA-256 hashes and saved to `SHA256SUMS.txt`.
- [x] **Bootstrap Data Ingestion:**
  - [x] `source_sites_ground_truth_FINAL.csv` (79,365 physical sites master).
  - [x] `site_daily_activity.parquet` (297,348 daily activity records).
  - [x] `MODEL_B_SOURCE_STATES_FINAL.csv` (79,365 states matching frozen counts 100%).
  - [x] `MODEL_C_EVENT_REPLAY_V3.parquet` (297,348 anomaly replay records).
- [x] **Evidence Datasets Ingestion:**
  - [x] `worldbank_gfmr_india_2025.csv` (174 gas flaring sites).
  - [x] `gem_gipt_india.csv` (962 power plants).
  - [x] `fsi_forest_fire_2025.csv` (262,100 forest wildfire perimeters).
  - [x] `icar_creams_crop_burn_2025.csv` (5,158 crop burning locations).
- [x] **Model Feature Synchronization:**
  - [x] Unpickled `MODEL_A_FINAL.joblib` and resolved the 33 vs 36 feature discrepancy.
  - [x] Verified that fitted pipeline requires exactly 33 features.
  - [x] Updated `backend/config/model_a_features.json` to 33 features.
  - [x] Exported embedded audit config to `backend/config/source/model_a_final_config.json`.
  - [x] Verified end-to-end inference pass on `MODEL_A_FINAL.joblib`.

---

### Phase 1: Backend Intelligence Engines
**Status:** **COMPLETED ✅**

- [x] **`source_resolver.py`:** Incremental 750m spatial resolver using Haversine BallTree query with ambiguity flagging and 3-detection candidate accumulator.
- [x] **`feature_builder.py`:** 33-feature extractor pipeline (T: 11, R: 10, S: 3, L: 9) matching `MODEL_A_FINAL.joblib` feature order with built-in SimpleImputer median fallback.
- [x] **`model_a.py`:** `ModelAEngine` wrapper executing XGBoost A-Core pipeline with frozen thresholds (0.405, 0.885, 0.975) and guarded Prithvi rescue logic (threshold: 0.965, never vetoes $\ge 0.885$).
- [x] **`model_b.py`:** `ModelBEngine` deterministic temporal state engine (5 states in precedence: REACTIVATED $\rightarrow$ NEW $\rightarrow$ PERSISTENT $\rightarrow$ DORMANT $\rightarrow$ INTERMITTENT) with confidence scoring. Tested against all 79,365 bootstrap sites: reproduced frozen 2025 counts with 100.00% exact match (61,890 dormant, 10,399 intermittent, 5,047 reactivated, 1,551 new, 478 persistent).
- [x] **`model_c.py`:** `ModelCEngine` online anomaly detector (cold-start minimum 5 active days check, median/MAD robust baseline, 4 anomaly groups, two-stage midrank percentile scoring). Verified against `MODEL_C_EVENT_REPLAY_V3.parquet` golden row ($\Delta < 10^{-6}$).
- [x] **Golden Regression Tests (`backend/tests/`):**
  - [x] `test_feature_builder.py`: 33 features validation and feature extraction on mock sequences.
  - [x] `test_model_a.py`: Decision threshold classes and guarded Prithvi rescue bounds.
  - [x] `test_model_b.py`: Synthetic transition cases and full 79,365-site frozen count verification.
  - [x] `test_model_c.py`: Cold-start protection and frozen golden row replay reproduction.
  - [x] `test_source_resolver.py`: Haversine distance, incremental candidate promotion, and spatial ambiguity detection.

---

### Phase 2: Live FIRMS Ingestion & 2026 Backfill
**Status:** **COMPLETED ✅**

- [x] **`firms_client.py`:** NASA FIRMS Area API client (NOAA-20 NRT, India bounding box `67,6,98,38`, 1–5 day chunking, rate limiting, and offline cache/mock fallback).
- [x] **`firms_ingestion.py`:** Idempotent ingestion pipeline with deterministic SHA-256 deduplication, incremental spatial resolution, and daily activity aggregation matching `site_daily_activity.parquet`.
- [x] **`backfill_firms_2026.py`:** Script and CLI to backfill detections from `2026-01-01` through deployment date in $\le 5$-day windows, updating daily activity and computing states.
- [x] **Golden Regression Tests (`backend/tests/`):**
  - [x] `test_firms_client.py`: Area API URL construction, day_range validation, CSV parsing, and offline cache fallback.
  - [x] `test_firms_ingestion.py`: Deterministic SHA-256 ID hashing, duplicate batch filtering, spatial resolution matching, and daily activity aggregation.
  - [x] `test_backfill_2026.py`: 5-day window partitioning and end-to-end dry-run execution.


---

### Phase 3: Decision & Alert Engine
**Status:** **COMPLETED ✅**

- [x] **`decision_engine.py`:** Deterministic A+B+C fusion policy matrix synthesizing identity, temporal state, and anomaly severity into operational alerts.
- [x] **Alert Taxonomy Implementation:** Full operational coverage across 10 official alert types (`CRITICAL_INDUSTRIAL_ANOMALY`, `HIGH_INDUSTRIAL_ANOMALY`, `INDUSTRIAL_REACTIVATION_ANOMALY`, `INDUSTRIAL_ELEVATION`, `UNKNOWN_CRITICAL_REVIEW`, `UNKNOWN_ANOMALY_REVIEW`, `NEW_SOURCE_REVIEW`, `NORMAL_INDUSTRIAL_OPERATION`, `NONINDUSTRIAL_ACTIVITY`, `NO_ALERT`).
- [x] **Alert Deduplication & Same-Day Escalation:** Stable SHA-256 fingerprinting on `(site_id, site_day, alert_type, model_stack_version)` with same-day incident escalation (`ELEVATED` $\rightarrow$ `ANOMALOUS` $\rightarrow$ `CRITICAL`).
- [x] **Frozen Policy Export:** Tested all A/B/C combinations, audited alert burden, and frozen `backend/config/decision_engine.json` (schema_version 1.0, status FROZEN).
- [x] **Regression Tests (`backend/tests/test_decision_engine.py`):** 13 unit tests verifying all 10 alert rules, escalation handling, and fingerprint determinism.


---

### Phase 4: PostgreSQL / PostGIS Database Layer
**Status:** **PENDING ⏳**

- [ ] Define SQLAlchemy declarative models for all 12 core tables (`firms_detections`, `source_sites`, `site_daily_activity`, `site_model_a`, `site_model_b`, `site_model_c`, `alerts`, `facility_evidence`, etc.).
- [ ] Spatial GiST indexing on point geometries.
- [ ] Set up Alembic migration environment.
- [ ] **`bootstrap_db.py`:** Script to load the 79k sites, 2025 daily activity, evidence tables, and precomputed states into PostGIS.

---

### Phase 5: Normalized FastAPI Endpoints
**Status:** **PENDING ⏳**

- [ ] `GET /api/v1/health` (service status, DB connectivity, model stack version).
- [ ] `GET /api/v1/stats` (global counts for header cards).
- [ ] `GET /api/v1/sites?bbox=&a_class=&b_state=&c_status=` (compact viewport GeoJSON).
- [ ] `GET /api/v1/sites/{site_id}` (full site intelligence summary).
- [ ] `GET /api/v1/sites/{site_id}/timeline` (daily FRP + Model C scores).
- [ ] `GET /api/v1/sites/{site_id}/evidence` (GEM, GFMR, FSI context).
- [ ] `GET /api/v1/sites/{site_id}/detections` (raw FIRMS detection records).
- [ ] `GET /api/v1/alerts` (active operational alert feed).
- [ ] `GET /api/v1/replay?date=` (historical date snapshot reconstruction).
- [ ] `GET /api/v1/stream/alerts` (Server-Sent Events / WebSocket real-time alert updates).

---

### Phase 6: OSIRIS Web Command Center (Frontend)
**Status:** **PENDING ⏳**

- [ ] **Center Map:** MapLibre GL JS + deck.gl WebGL viewport with GPU site point clustering, raw detection layer, and alert pulse styling.
- [ ] **Left Filter Panel:** Multi-layer toggles (A identity, B temporal states, C anomaly severity, evidence layers, date range slider).
- [ ] **Right Site Intelligence Drawer:**
  - [ ] Overview tab (provenance, confidence, current FRP).
  - [ ] Timeline tab (Recharts/ECharts visualization of daily FRP and Model C scores).
  - [ ] Satellite tab (HLS scene viewer, cloud screening badge, Prithvi score if triggered).
  - [ ] Evidence tab (nearby power plants, refineries, land-cover composition).
  - [ ] Raw FIRMS tab (detection log table).
- [ ] **Top Status Bar:** Mode toggle (LIVE vs. REPLAY), active model version badge, system health.
- [ ] **Bottom / Secondary Timeline:** Historical playback slider for replay mode.

---

### Phase 7: Live Scheduling & Async Queues
**Status:** **PENDING ⏳**

- [ ] APScheduler / background polling process (15-minute FIRMS NRT cycle).
- [ ] Immediate incremental resolution and Model B/C update for touched sites.
- [ ] Daily global Model B state recalculation.
- [ ] Asynchronous worker queue for Earthdata HLS satellite patch download and Prithvi visual rescue.

---

### Phase 8: Demo Replay & Hardening
**Status:** **PENDING ⏳**

- [ ] Curate 3–4 dramatic historical scenarios for hackathon judging (e.g. refinery flare anomaly, reactivation after long dormancy, wildfire vs. factory contrast).
- [ ] Offline demo cache mechanism so the presentation is never disrupted by network dropouts.
- [ ] End-to-end documentation and demo walkthrough script.
