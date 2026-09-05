---
title: 07 Firms Integration
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["12. Live NASA FIRMS Integration and 2026 Backfill", "13. HLS / Prithvi Operational Integration", "14. External GIS and Facility Evidence Layers"]
status: authoritative
---

# 12. Live NASA FIRMS Integration and 2026 Backfill

## 12.1 Official FIRMS Area API

The backend should use the NASA FIRMS Area API, not browser-side calls. The official CSV endpoint pattern is:

> https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{WEST,SOUTH,EAST,NORTH}/{DAY_RANGE}[/{DATE}]

- DAY_RANGE is 1-5 days per Area API query.

- Use a secure free MAP_KEY. NASA documents a default limit of 5,000 transactions per 10-minute interval.

- For the India working extent, start with bbox approximately 67,6,98,38 and refine if the operational boundary is changed.

- Primary live source should initially be VIIRS_NOAA20_NRT for continuity with the NOAA-20-trained project.

- VIIRS_NOAA21_NRT can be ingested as a corroborating layer, but do not silently mix it into Model A feature distributions until a multi-sensor harmonization/regression audit is completed.

## 12.2 Current satellite product caution

NASA FIRMS currently supports NOAA-20 and NOAA-21 NRT products. NASA also states that Suomi-NPP delivery is scheduled to cease on 01 November 2026; therefore the production design should not depend on S-NPP. The platform should prioritize NOAA-20/NOAA-21.

## 12.3 Mandatory 2026 backfill

| **Before live mode** Backfill from 2026-01-01 through the deployment date. The frozen 2025 B/C snapshots cannot be used as if they were current in September 2026. |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|

> 1\. Call FIRMS data_availability endpoint to determine valid NOAA-20 data ranges.
>
> 2\. Download 2026 in \<=5-day windows using the Area API or an archived source if already available.
>
> 3\. Normalize schemas and deduplicate by sensor/satellite/time/location/version identifiers.
>
> 4\. Incrementally assign each detection to an existing frozen site or candidate source.
>
> 5\. Rebuild/update site_daily_activity through the current date.
>
> 6\. Recompute Model A touched/new sites, Model B as-of current date, and Model C chronological state.
>
> 7\. Write a new model-stack snapshot and mark the 2025 snapshot as historical.

## 12.4 Live polling cadence

A 15-minute backend poll interval is a reasonable prototype cadence for responsiveness and deduplication, but it must not be interpreted as 15-minute satellite-observation latency. NASA states that global FIRMS NRT active-fire data are generally available within about 3 hours of satellite observation. Poll the most recent 1-day window, upsert/deduplicate, record data freshness, and process only new or revised detections.

## 12.5 Ingestion idempotency

- Every detection must have a deterministic unique key. Prefer official sensor/time/location/version fields; otherwise hash a normalized composite.

- Upsert NRT records instead of blindly appending when FIRMS replaces RT/URT records with NRT records.

- Store source_sensor and source_version for provenance.

- Keep raw payload columns in a JSONB field in addition to normalized columns.

# 13. HLS / Prithvi Operational Integration

## 13.1 Prithvi is asynchronous optional evidence

Do not run a 300M-parameter foundation model for every map point on every API request. A-Core is immediate. Only sites in the A-Core uncertainty band 0.405-0.885 should be queued for HLS/Prithvi, and only when a suitable image exists.

## 13.2 HLS asset mapping used in the pilot

| **HLS product** | **Six assets mapped to model channels** |
|-----------------|-----------------------------------------|
| HLSS30          | B02, B03, B04, B8A, B11, B12            |
| HLSL30          | B02, B03, B04, B05, B06, B07            |

## 13.3 Pilot preprocessing

- 224 x 224 patch centered on the source.

- Local cloud screening from Fmask; pilot rejected sites above approximately 25% local cloud after candidate selection.

- Six channels normalized using the official Prithvi config mean/std.

- A single good scene is repeated across four frames in the current pilot. This tests morphology, not genuine temporal sequence learning.

- HLS patch and embedding results should be cached by site_id and acquisition date.

- Pilot retrieval details: search +/-120 days around the source reference date in a ~0.001 degree point-centered box; request up to two HLSS30 candidates with catalog cloud_cover \<=35%, then fall back to up to two HLSL30 candidates. Apply local Fmask screening and accept a patch only when local cloud fraction \<=25%. The 270-site extraction used a resumable manifest/cache and up to four concurrent workers; reduce concurrency if Earthdata throttling appears.

## 13.4 Direct model loading

Deployment should use the direct official Prithvi files and avoid the TerraTorch/TorchGeo dependency combination that caused incompatibility in Colab. Pin a specific Hugging Face revision and keep the following files in a model artifact cache: Prithvi_EO_V2_300M.pt, config.json and prithvi_mae.py.

## 13.5 Live fallback

> if A-Core is CORE/STRONG: return immediately  
> elif A-Core is uncertain and cached HLS/Prithvi exists: evaluate rescue  
> elif A-Core is uncertain and imagery unavailable: return UNKNOWN with prithvi_status=UNAVAILABLE/PENDING

# 14. External GIS and Facility Evidence Layers

These datasets should be visible to analysts and can support positive corroboration, but they must remain outside the production A-Core feature vector to avoid circularity and brittle negative vetoes.

| **Source / file**                               | **Spatial status**                              | **Recommended role**                                                              |
|-------------------------------------------------|-------------------------------------------------|-----------------------------------------------------------------------------------|
| World Bank GFMR / worldbank_gfmr_india_2025.csv | Coordinates available                           | Industrial/faring evidence layer; training truth where independently appropriate. |
| GEM GIPT / gem_gipt_india.csv                   | Coordinates available                           | Power-plant/facility evidence layer.                                              |
| GEM GCCT workbook                               | Coordinate pair + exact/approx field available  | Cement/concrete facility evidence; coordinate quality displayed.                  |
| GEM GIST workbook                               | No usable coordinates in downloaded workbook    | Identity/reference only; do not guess coordinates.                                |
| GEM GCMT workbook                               | No usable coordinates in downloaded workbook    | Identity/reference only; do not guess coordinates.                                |
| PPAC refining workbook                          | No coordinates                                  | Identity/capacity reference only.                                                 |
| OSM / Geofabrik                                 | Rich industrial/power/works/mine/quarry vectors | UI context and candidate evidence; not negative truth.                            |
| ESA WorldCover                                  | 10 m land-cover COGs                            | Static Model A L features + map layer.                                            |
| FSI forest fire                                 | Affirmative negative source evidence            | Ground-truth/reference layer.                                                     |
| ICAR CREAMS crop burn                           | Affirmative negative source evidence            | Ground-truth/reference layer.                                                     |

## 14.1 Known external files

> /content/drive/MyDrive/SIH26162/india_external_sources/worldbank_gfmr_india_2025.csv  
> /content/drive/MyDrive/SIH26162/india_external_sources/gem_gipt_india.csv  
> /content/drive/MyDrive/SIH26162/india_external_sources/fsi_forest_fire_2025.csv  
> /content/drive/MyDrive/SIH26162/india_external_sources/icar_creams_crop_burn_2025.csv  
> 1787032950_Refining_Capacity_Historic.xlsx  
> Global Coal Mine Tracker, August 2026.xlsx  
> Plant-level_data_Global_Iron_and_Steel_Tracker_June_2026_V1.xlsx  
> Plant-level data - Global Cement and Concrete Tracker - July 2026 - Standard Copy V1.xlsx

**Artifact packaging gate:** the paths in this document define the frozen runtime contract. Before deployment, verify every required file exists in Drive/repository, generate SHA-256 checksums, and fail startup if an authoritative artifact/config is missing or mismatched.
