---
title: 11 Testing Roadmap
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["24. Testing and Acceptance Criteria", "25. Exact Implementation Roadmap"]
status: authoritative
---

# 24. Testing and Acceptance Criteria

## 24.1 Unit tests

| **Area**        | **Minimum tests**                                                                                                        |
|-----------------|--------------------------------------------------------------------------------------------------------------------------|
| Feature builder | Golden-row test: backend features exactly equal frozen notebook output for known site_ids.                               |
| Source resolver | Known historical detections map back to the same site; boundary and ambiguous multi-site cases audited.                  |
| Model A         | Known frozen test rows reproduce stored core probabilities within tolerance; guarded thresholds exact.                   |
| Model B         | Synthetic timelines cover all five states and every precedence edge case.                                                |
| Model C         | Golden chronological site histories reproduce V3 scores; no future leakage; long-gap reset; cold start; same-day update. |
| Decision engine | Exhaustive A/B/C combination matrix produces stable alert types and no accidental industrial claim from UNKNOWN.         |
| FIRMS ingestion | Idempotent re-fetch does not duplicate detections; version updates are upserted.                                         |
| API             | Schemas stable; bbox filters correct; unauthorized admin routes protected if added.                                      |
| Frontend        | Layer filters, site selection, timeline, live/replay switch and alert jump-to-map operate correctly.                     |

## 24.2 Regression acceptance before web demo

> 1\. Backfill 2026 and confirm site counts / assignment rates are plausible.
>
> 2\. Run Model A golden sample and ensure probabilities/decisions match frozen artifacts.
>
> 3\. Run Model B on the original 2025 cutoff and reproduce the exact frozen counts: 61,890 dormant; 10,399 intermittent; 5,047 reactivated; 1,551 new; 478 persistent.
>
> 4\. Run Model C on the original V3 replay and reproduce event/status distributions within deterministic equality where platform libraries allow.
>
> 5\. Verify current backfilled snapshot contains no stale 2025 as_of_date fields.
>
> 6\. Verify Prithvi unavailable path returns A-Core result rather than raising an API error.
>
> 7\. Verify 6,743-style insufficient-history behavior is represented as INSUFFICIENT_HISTORY rather than NORMAL when equivalent cold-start cases exist after backfill.

# 25. Exact Implementation Roadmap

| **Phase**                  | **Deliverable**                                                                                                                                                         |
|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| P0 - Freeze packaging      | 1\. Copy frozen artifacts to repository models/. 2. Generate checksums. 3. Write model_a/model_b/model_c configs. 4. Write a stack manifest with version 2026-09-04-r1. |
| P1 - Backend engines       | Implement feature_builder.py, model_a.py, model_b.py, model_c.py, source_resolver.py. Add golden regression tests before any UI.                                        |
| P2 - 2026 backfill         | Implement FIRMS client + 5-day backfill script. Populate detections/site history through current date. Recompute B/C and touched A.                                     |
| P3 - Decision engine       | Implement the initial rule matrix, review generated alert burden, then freeze decision_engine.json.                                                                     |
| P4 - Database              | Create PostGIS schema/migrations. Bootstrap frozen sites, historical daily activity, evidence and current model status.                                                 |
| P5 - API                   | Implement health/stats/sites/site-detail/timeline/alerts/layers/replay endpoints and SSE/WebSocket updates.                                                             |
| P6 - Command-center UI     | Build MapLibre/deck.gl map, layer/filter panel, alert feed, detail drawer, timeline, evidence and raw FIRMS tabs.                                                       |
| P7 - Live scheduling       | Poll FIRMS every ~15 min, process touched sites, daily B refresh, asynchronous HLS/Prithvi queue.                                                                       |
| P8 - Replay/demo hardening | Prepare deterministic historical scenarios, demo scripts, graceful offline/cache behavior and monitoring.                                                               |
| P9 - Post-SIH improvements | Multi-sensor NOAA-20/21 harmonization, true 4-date Prithvi, peer-baseline cold start for C, verified incident ground truth and production alert calibration.            |

## 25.1 Do this next

| **Next coding milestone** Build the unified backend engines + stack manifest first, then run the 2026 FIRMS backfill. Starting the frontend before these two steps will lead to duplicated logic and stale temporal outputs. |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
