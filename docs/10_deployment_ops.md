---
title: 10 Deployment Ops
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["20. End-to-End Live Processing Flow", "21. Historical Replay Mode", "22. Deployment, Scheduling and Performance", "23. Security, Secrets, Licensing and Provenance"]
status: authoritative
---

# 20. End-to-End Live Processing Flow

<img src="assets/live_flow.png" style="width:6.7in;height:3.58526in" />

## 20.1 Every 15-minute ingestion cycle

> 1\. Fetch recent NOAA-20 NRT FIRMS detections for India from the backend FIRMS client.
>
> 2\. Normalize schema and upsert/deduplicate records.
>
> 3\. For each new/updated detection, perform incremental 750 m source assignment; unresolved points go to candidate_sources.
>
> 4\. Update the current site-day aggregate for touched source sites.
>
> 5\. Recompute A-Core features for touched/new stable sites using the exact production feature builder. Static WorldCover features are cached.
>
> 6\. If A-Core falls in 0.405-0.885, look for cached Prithvi evidence or enqueue an HLS/Prithvi task. Do not block immediate A-Core result.
>
> 7\. Recompute Model B for touched sites immediately. Run a daily global refresh because days_since_last can change even without a new detection.
>
> 8\. Rescore Model C for the touched current site-day using prior days only. If history is insufficient, return INSUFFICIENT_HISTORY.
>
> 9\. Run the decision engine and upsert/escalate alerts.
>
> 10\. Commit current site status to PostGIS and publish alert/site-status changes through SSE/WebSocket.
>
> 11\. Frontend updates the map without rerunning model logic.

## 20.2 Daily boundary behavior

During the same UTC date, site_daily_activity is updated in place as more detections arrive. Model C repeatedly scores the growing current-day aggregate against prior active days. On the next date, the completed previous day becomes part of history. Model B global time-dependent state refresh should run at least once daily even if no new detections arrive. Persist each completed day's Model C output in site_daily_inference so replay/timeline endpoints never depend on only the latest site_model_c row.

# 21. Historical Replay Mode

Replay mode is recommended for judging because a live critical event cannot be guaranteed during a presentation. The user selects a historical timestamp/date and the platform reconstructs the map using only information available up to that point.

## 21.1 Replay requirements

- Never use the current final site state when replaying an earlier date.

- Model B must be computed using replay_date as as_of_date.

- Model C must use the existing chronological event score already computed at that date, or rerun chronologically if necessary.

- Model A may use a historically materialized snapshot if available; for the prototype, clearly label if source identity is using the final 2025 site classification while B/C are replayed.

- Timeline play controls should allow the judge to watch source activation, reactivation and anomaly escalation.

# 22. Deployment, Scheduling and Performance

## 22.1 Prototype deployment

| **Layer**             | **Recommended prototype choice**                                                                              |
|-----------------------|---------------------------------------------------------------------------------------------------------------|
| Database              | PostgreSQL 16 + PostGIS                                                                                       |
| Backend API           | FastAPI + Uvicorn                                                                                             |
| Background scheduling | Separate worker process using APScheduler/cron for prototype; move to Celery/Redis only if scale requires it. |
| Frontend              | Next.js / React / TypeScript                                                                                  |
| Map                   | MapLibre GL JS + deck.gl                                                                                      |
| Model A-Core          | Loaded once at backend/worker startup.                                                                        |
| Prithvi               | Lazy-loaded GPU worker if available; otherwise cached/precomputed or skipped with explicit status.            |
| Model B               | Pure Python engine; negligible inference cost.                                                                |
| Model C               | Python/NumPy engine + frozen calibration artifact; incremental site-day scoring.                              |
| Deployment            | Docker Compose for SIH demo; separate frontend, backend, worker, postgres services.                           |

## 22.2 Performance rules

- Never run DBSCAN over the full archive on a web request.

- Never run Prithvi for all 79k sites synchronously.

- Never load a full year of FIRMS into memory per API request.

- Use spatial bounding-box queries and server-side filtering for the map.

- Cache HLS patches, Prithvi embeddings and facility evidence.

- Load model artifacts once per worker process.

- Materialize latest site status for fast frontend reads.

# 23. Security, Secrets, Licensing and Provenance

## 23.1 Secrets

- FIRMS_MAP_KEY must exist only in backend environment/secret storage.

- Earthdata credentials/token must never be embedded in frontend JavaScript or committed to Git.

- Database credentials remain server-side.

- Use .env.example with empty placeholders; actual .env is gitignored.

## 23.2 Artifact provenance

- Create SHA256SUMS.txt for every frozen model/config artifact included in deployment.

- Store model_stack_version on every site result and alert.

- Pin the Prithvi Hugging Face repository revision instead of always downloading main.

- Record data source/version and ingestion time for each FIRMS detection.

## 23.3 External model/data licenses

Prithvi-EO-2.0-300M is published under Apache-2.0 on Hugging Face. Preserve its license/notice when redistributing weights/code. For facility datasets, OSM and other third-party sources, retain each provider's attribution and usage terms in the final platform.

If the team reuses or forks source code from the referenced OSIRIS/DigIntLab implementation rather than merely adopting a similar interaction pattern, preserve its MIT license/copyright notice and separately review any data-source license file bundled with that repository.
