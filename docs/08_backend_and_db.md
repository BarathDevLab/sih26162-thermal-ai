---
title: 08 Backend And Db
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["15. Runtime Packaging - How A, B and C Deploy Together", "16. Backend Architecture and Repository Structure", "17. PostgreSQL / PostGIS Data Model", "18. FastAPI Contract"]
status: authoritative
---

# 15. Runtime Packaging - How A, B and C Deploy Together

## 15.1 Why the artifacts are different

| **Component**   | **What is serialized**                                              | **What runs at inference**                                                                                   |
|-----------------|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| A-Core          | Full fitted sklearn/XGBoost pipeline in MODEL_A_FINAL.joblib        | Load artifact -\> feature vector -\> predict_proba.                                                          |
| A-Image         | Lightweight classifier/config + official Prithvi foundation weights | Load/cached encoder -\> HLS patch -\> embedding -\> probability -\> guarded rescue.                          |
| Model B         | No fitted estimator required                                        | Python rules + JSON thresholds operate on site history.                                                      |
| Model C         | Calibration references/config in MODEL_C_V3_FROZEN.joblib           | Python statistical engine computes current group scores and maps them through frozen calibration references. |
| Decision Engine | JSON policy only after freeze                                       | Python rules combine A+B+C into alerts.                                                                      |

## 15.2 Uniform backend interfaces

> class ModelAEngine:  
> def predict(self, site_features, imagery=None): ...  
>   
> class ModelBEngine:  
> def predict(self, site_history, as_of_date): ...  
>   
> class ModelCEngine:  
> def score(self, prior_history, current_site_day): ...  
>   
> class DecisionEngine:  
> def combine(self, a_result, b_result, c_result): ...

The frontend never needs to know whether a result came from XGBoost, deterministic rules or robust statistics. It receives one normalized site-status object.

# 16. Backend Architecture and Repository Structure

> sih26162-platform/  
> ├── backend/  
> │ ├── app/  
> │ │ ├── main.py  
> │ │ ├── api/  
> │ │ │ ├── sites.py  
> │ │ │ ├── alerts.py  
> │ │ │ ├── timeline.py  
> │ │ │ ├── layers.py  
> │ │ │ ├── replay.py  
> │ │ │ └── health.py  
> │ │ ├── engines/  
> │ │ │ ├── model_a.py  
> │ │ │ ├── model_b.py  
> │ │ │ ├── model_c.py  
> │ │ │ ├── decision_engine.py  
> │ │ │ └── source_resolver.py  
> │ │ ├── services/  
> │ │ │ ├── firms_client.py  
> │ │ │ ├── firms_ingestion.py  
> │ │ │ ├── hls_service.py  
> │ │ │ ├── prithvi_worker.py  
> │ │ │ ├── feature_builder.py  
> │ │ │ └── snapshot_service.py  
> │ │ ├── db/  
> │ │ │ ├── models.py  
> │ │ │ ├── session.py  
> │ │ │ └── migrations/  
> │ │ ├── schemas/  
> │ │ └── config.py  
> │ ├── models/  
> │ │ ├── MODEL_A_FINAL.joblib  
> │ │ ├── MODEL_A_PRITHVI_FINAL.joblib  
> │ │ ├── MODEL_C_V3_FROZEN.joblib  
> │ │ └── prithvi/  
> │ │ ├── Prithvi_EO_V2_300M.pt  
> │ │ ├── config.json  
> │ │ └── prithvi_mae.py  
> │ ├── config/  
> │ │ ├── model_a.json  
> │ │ ├── model_b.json  
> │ │ ├── model_c.json  
> │ │ └── decision_engine.json  
> │ ├── scripts/  
> │ │ ├── bootstrap_db.py  
> │ │ ├── backfill_firms_2026.py  
> │ │ ├── run_ingestion_once.py  
> │ │ └── rebuild_snapshot.py  
> │ ├── tests/  
> │ └── requirements.txt  
> ├── frontend/  
> │ ├── app/  
> │ ├── components/map/  
> │ ├── components/panels/  
> │ ├── components/timeline/  
> │ └── services/api.ts  
> ├── docker-compose.yml  
> ├── .env.example  
> ├── SHA256SUMS.txt  
> └── README.md

## 16.1 Recommended backend dependencies

fastapi, uvicorn, pydantic, sqlalchemy, psycopg, geoalchemy2, pandas, numpy, scikit-learn, xgboost, joblib, scipy, shapely, pyproj, rasterio, earthaccess, requests/httpx, python-dotenv, orjson, apscheduler (prototype scheduling), torch, timm, einops and huggingface_hub. Keep TerraTorch and TorchGeo out of the production dependency set unless a later compatibility audit specifically reintroduces them.

# 17. PostgreSQL / PostGIS Data Model

## 17.1 Core tables

| **Table**            | **Minimum fields / purpose**                                                                                                                                                                                                                        |
|----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| firms_detections     | raw_id PK, sensor, satellite, latitude, longitude, geometry, acq_date, acq_time, frp, brightness fields, confidence, daynight, version, raw_payload JSONB, ingested_at, source_site_id nullable                                                     |
| source_sites         | site_id PK, cluster_id/history id, centroid geometry, latitude, longitude, created_at, promoted_at, status, static WorldCover fractions, spatial stats, latest_seen                                                                                 |
| candidate_sources    | candidate_id PK, geometry/centroid, first_seen, last_seen, detection_count, status, promoted_site_id                                                                                                                                                |
| site_daily_activity  | site_id + acq_date PK, detections, mean_frp, max_frp, optional min/median FRP, source sensor counts, updated_at                                                                                                                                     |
| site_model_a         | site_id PK, core_probability, class, decision, prithvi_probability nullable, prithvi_status, model_version, computed_at                                                                                                                             |
| site_model_b         | site_id PK, state, confidence, reason, days_since_last, active_days windows, gap fields, model_version, computed_at                                                                                                                                 |
| site_model_c         | site_id PK, event_date, operational_status, c_score, c_raw, group scores/percentiles, evidence_99, drivers, history counts, model_version, computed_at. This table is the materialized latest status only.                                          |
| alerts               | alert_id PK, site_id, alert_type, severity, headline, reason_codes JSONB, fingerprint UNIQUE, status, created_at, updated_at, acknowledged_by nullable                                                                                              |
| facility_evidence    | evidence_id PK, source_name, facility_name, facility_type, geometry nullable, coordinate_quality, source_url/id, attributes JSONB                                                                                                                   |
| imagery_cache        | site_id, acquisition_date, HLS product, cloud_fraction, patch_uri, embedding_uri, prithvi_probability, status, updated_at                                                                                                                           |
| model_versions       | component, version, artifact_sha256, config JSONB, activated_at, is_active                                                                                                                                                                          |
| ingestion_runs       | run_id, source, started_at, ended_at, records_read, inserted, updated, failed, status, error_summary                                                                                                                                                |
| site_daily_inference | site_id + acq_date PK/FK, model_c_status, c_score, c_raw, group scores/percentiles, evidence_99, drivers, model_c_version, optional replayed model_b_state/confidence, computed_at. Historical model-output table used by timeline and replay APIs. |

## 17.2 Required indexes

- GIST index on firms_detections.geometry and source_sites.centroid.

- Composite indexes on site_daily_activity(site_id, acq_date DESC), site_daily_inference(site_id, acq_date DESC) and alerts(severity, updated_at DESC).

- Unique deduplication constraint/hash on normalized FIRMS detection identity.

- Index site_model_a.class, site_model_b.state, site_model_c.operational_status and site_daily_inference.model_c_status for map/replay filters.

# 18. FastAPI Contract

## 18.1 Core endpoints

| **Method / endpoint**                               | **Purpose**                                         |
|-----------------------------------------------------|-----------------------------------------------------|
| GET /api/v1/health                                  | Service, database and active model versions.        |
| GET /api/v1/stats                                   | Global/current counts for map header and dashboard. |
| GET /api/v1/sites?bbox=&a_class=&b_state=&c_status= | Viewport-filtered source sites.                     |
| GET /api/v1/sites/{site_id}                         | Full current A/B/C + alert + evidence summary.      |
| GET /api/v1/sites/{site_id}/timeline                | Daily FIRMS history + C score/level.                |
| GET /api/v1/sites/{site_id}/detections              | Raw FIRMS detections for analyst detail.            |
| GET /api/v1/sites/{site_id}/imagery                 | Available HLS/Prithvi imagery metadata.             |
| GET /api/v1/sites/{site_id}/evidence                | GEM/GFMR/OSM/facility evidence.                     |
| GET /api/v1/alerts                                  | Current alert feed.                                 |
| GET /api/v1/layers/firms                            | Recent raw FIRMS layer; viewport/date filtered.     |
| GET /api/v1/replay?date=                            | Historical snapshot for replay mode.                |
| GET /api/v1/stream/alerts                           | SSE/WebSocket stream for alert changes.             |

## 18.2 Map endpoint performance

Do not return all detailed fields for 79k sites on every map request. Return a compact viewport GeoJSON/JSON payload containing site_id, lat/lon, A class/probability band, B state, C status/score, alert severity and latest_seen. Load the full detail panel only after a site is selected.
