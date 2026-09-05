---
title: 01 Data And Ground Truth
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["5. Data Foundation and 750 m Source Resolver", "6. Ground Truth and Training Data Construction"]
status: authoritative
---

# 5. Data Foundation and 750 m Source Resolver

## 5.1 Historical FIRMS source

The frozen source catalogue was built from the NOAA-20 VIIRS archive file /content/drive/MyDrive/SIH26162/data/DL_FIRE_J1V-C2_794660.zip. The India working extent used during processing was approximately latitude 6-38 degrees and longitude 67-98 degrees. The historical time window used by Model B/C is 2025-01-01 through 2025-12-31.

## 5.2 Source clustering

> DBSCAN(metric='haversine', eps=750 / EarthRadius, min_samples=3)  
> unit = resolved source_site, not hotspot row

The 750 m value is a neighborhood link radius, not a maximum cluster diameter. DBSCAN can chain nearby detections, which is why the larger 1000 m candidate was rejected despite a very small weak-label score increase.

## 5.3 750 m vs 1000 m audit

| **Metric**                | **750 m**        | **1000 m**              | **Interpretation**                                 |
|---------------------------|------------------|-------------------------|----------------------------------------------------|
| Common-site weak-label F1 | 0.7257           | 0.7335                  | Only +0.78 percentage point for 1000 m.            |
| Multi-child merges        | Lower / baseline | 3,888                   | 1000 m merges many 750 m micro-sites.              |
| P90 child separation      | \-               | 6.014 km                | Far larger than an intended industrial micro-site. |
| Maximum child separation  | \-               | 54.573 km               | Clear chaining failure.                            |
| Extreme example           | \-               | 47-child merged cluster | Physically unacceptable source identity.           |

| **Frozen decision** 750 m / min_samples=3 is the physical source baseline. Do not rerun a 1000 m resolver in the web implementation. |
|--------------------------------------------------------------------------------------------------------------------------------------|

## 5.4 Live source resolution must be incremental

Do not rerun full-year DBSCAN every time new FIRMS data arrives. Store frozen sites and historical detection geometry in PostGIS. For each new point, search for existing site membership within 750 m of historical site detections. If multiple frozen sites qualify, assign to the nearest site and record an AMBIGUOUS_ASSIGNMENT audit flag rather than merging frozen sites.

- No match: write the point to candidate_sources.

- Candidate detections accumulate spatially using the same 750 m neighborhood logic.

- Promote a candidate to a permanent source only after at least 3 spatially consistent detections, matching the training-time min_samples requirement.

- On promotion, allocate a new stable site_id and compute static land-cover features once.

Streaming-equivalence requirement: the incremental resolver is a deployment approximation to frozen batch DBSCAN graph membership. Before activation, replay historical detections in time order and verify that assignments reproduce frozen site_ids at a high rate. If a new detection is within 750 m of more than one frozen site, preserve both candidates in the audit record and do not merge frozen sites automatically.

# 6. Ground Truth and Training Data Construction

## 6.1 Ground-truth philosophy

The project explicitly rejected the shortcut “far from known industry = nonindustrial.” Industrial labels require affirmative facility/reference/human evidence. Nonindustrial labels require affirmative wildfire, forest-fire, crop-burning, natural or manual evidence. Sites without adequate evidence remain UNKNOWN. Conflicting evidence remains CONFLICT_REVIEW.

## 6.2 Evidence metadata

> gt_source, gt_authority, gt_country, gt_geographic_scope, gt_class,  
> source_independence, coordinate_quality, label_confidence

## 6.3 Final source master

| **Label status** | **Count** | **Notes**                                                      |
|------------------|-----------|----------------------------------------------------------------|
| INDUSTRIAL       | 808       | Final supervised positive sites.                               |
| NONINDUSTRIAL    | 22,902    | Affirmative negative evidence.                                 |
| UNKNOWN          | 55,552    | No adequate affirmative truth; preserved.                      |
| CONFLICT_REVIEW  | 103       | Evidence conflict; excluded from ordinary supervised training. |
| TOTAL            | 79,365    | All frozen source sites.                                       |

Within the full source master, evidence tiers include 251 GOLD and 660 SILVER_A records; these totals also include the 103 conflict-review records. The final supervised industrial subset consists of 205 GOLD + 603 SILVER_A = 808 positives.

## 6.4 Silver-A review history

- 83 reviewed candidates: 66 INDUSTRIAL, 12 UNCERTAIN, 5 NONINDUSTRIAL.

- Generic INSIDE_OSM_INDUSTRIAL was judged too weak and moved out of Silver-A.

- The revised acceptance logic retained 63 reviewed candidates: 55 INDUSTRIAL, 8 UNCERTAIN, 0 NONINDUSTRIAL among the accepted subset.

- OSM-specific failures were concentrated in weak quarry/resource-coal contexts; these are not treated as standalone strong truth without corroboration.

## 6.5 Key training files

| **Path**                                                                                  | **Purpose**                                                   |
|-------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| /content/drive/MyDrive/SIH26162/model_a_final/built/source_sites_ground_truth_FINAL.csv   | All source sites with final truth status / evidence metadata. |
| /content/drive/MyDrive/SIH26162/model_a_final/built/model_a_supervised_with_folds.csv     | Final supervised dataset with frozen geographic folds.        |
| /content/drive/MyDrive/SIH26162/model_a_final/built/model_a_development_FULL_ENV.csv      | Full enriched development pool.                               |
| /content/drive/MyDrive/SIH26162/model_a_final/built/model_a_internal_holdout_FULL_ENV.csv | Frozen natural-distribution holdout.                          |
| /content/drive/MyDrive/SIH26162/model_a_final/built/model_a_internal_holdout.csv          | Pre-enrichment holdout / audit snapshot.                      |
