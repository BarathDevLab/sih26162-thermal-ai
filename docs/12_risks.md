---
title: 12 Risks
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["26. Risks, Limitations and Future Work"]
status: authoritative
---

# 26. Risks, Limitations and Future Work

| **Risk / limitation**                            | **Current mitigation**                         | **Future improvement**                                                                   |
|--------------------------------------------------|------------------------------------------------|------------------------------------------------------------------------------------------|
| Only 2025 history currently frozen               | Mandatory 2026 backfill before live use        | Continuous ingestion + periodic archive reconciliation.                                  |
| Model C site-specific coverage is sparse         | Use INSUFFICIENT_HISTORY honestly              | Add peer-group cold-start baseline as a separate, clearly labeled fallback.              |
| Prithvi pilot is small and single-scene repeated | Guarded optional rescue only                   | Larger uncertainty-band validation and four real HLS acquisitions.                       |
| No verified anomaly incident GT                  | Do not claim accuracy                          | Build incident/event benchmark from reports/industrial fire datasets and analyst review. |
| A-Core trained on NOAA-20 lineage                | Use NOAA-20 primary live features              | Sensor harmonization and regression before multi-sensor feature fusion.                  |
| Facility data coverage incomplete                | Evidence-only; UNKNOWN preserved               | Add validated geocoded registries without guessed coordinates.                           |
| OSM circularity                                  | Excluded from A-Core                           | Use only UI evidence and separately audited positive corroboration.                      |
| Alert policy not yet calibrated                  | Start deterministic and audit burden           | Collect analyst feedback and incident truth; version policy.                             |
| Prithvi compute / HLS latency                    | Asynchronous and optional                      | GPU worker / precompute / caching / lighter student model if necessary.                  |
| Map volume and bandwidth                         | BBox/filter endpoints + materialized snapshots | Vector tiles if scale grows substantially.                                               |
