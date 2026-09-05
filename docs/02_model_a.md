---
title: 02 Model A
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["7. Model A - Source Identity", "Appendix A. Exact Model A Feature Set"]
status: authoritative
---

# 7. Model A - Source Identity

<img src="assets/model_a.png" style="width:6.7in;height:3.58526in" />

## 7.1 Deployment definition

| **Frozen definition** Model A = A-Core (XGBoost T+R+S+L) + optional A-Image (Prithvi-EO-2.0-300M) under a guarded rescue policy. GIS/OSM/GEM are evidence layers, not required AI prediction inputs. |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## 7.2 A-Core algorithm

The core is a serialized scikit-learn Pipeline containing median imputation and XGBoost binary classification. Deployment must load the serialized pipeline rather than manually recreating training hyperparameters. The documented training family used 300 estimators, depth 3, learning rate .035, min_child_weight 2, subsample .85, colsample_bytree .85, reg_alpha .05, reg_lambda 2, binary:logistic objective, logloss evaluation, class weighting from NEG/POS, random_state 42 and hist tree method.

## 7.3 Production feature families

| **Family**             | **Meaning**                       | **Count** | **Production status** |
|------------------------|-----------------------------------|-----------|-----------------------|
| T                      | Thermal intensity/statistics      | 13        | INCLUDED              |
| R                      | Recurrence / persistence behavior | 11        | INCLUDED              |
| S                      | Spatial dispersion                | 3         | INCLUDED              |
| L                      | WorldCover land-cover fractions   | 9         | INCLUDED              |
| N                      | Nighttime lights                  | 5         | EXCLUDED              |
| OSM distances          | Industrial/power/works proximity  | \-        | EXCLUDED from A-Core  |
| FIRMS type/static clue | Type fractions / persistence_seed | \-        | EXCLUDED              |

Total production feature count: 36. The exact list is provided in Appendix A. Model A feature semantics must match training exactly. In particular, Model A active_days_7/30/90/365 features were computed relative to the source's own last detection; do not substitute Model B's observation-end semantics.

## 7.4 Why NTL was dropped

Nighttime light features produced no reliable holdout ROC gain and increased false positives in high-built / high-NTL negatives. The selected production architecture is M2_NO_NTL = T+R+S+L.

## 7.5 Geographic split and final holdout

Sites were grouped into 0.5-degree geographic blocks. A five-fold StratifiedGroupKFold split with random_state=42 was used. Fold 0 was frozen as the internal natural-distribution holdout before performance inspection. Development uses folds 1-4.

| **Dataset**    | **Sites** | **Industrial** | **Nonindustrial** |
|----------------|-----------|----------------|-------------------|
| Development    | 19,038    | 639            | 18,399            |
| Frozen holdout | 4,672     | 169            | 4,503             |

## 7.6 Production A-Core thresholds

| **Band** | **Threshold** | **Operational meaning**                                                    | **Holdout precision** | **Holdout recall** | **Specificity** |
|----------|---------------|----------------------------------------------------------------------------|-----------------------|--------------------|-----------------|
| LOW      | 0.405         | Below this: NONINDUSTRIAL; above this uncertain/positive processing begins | 0.4894                | 0.9527             | 0.9627          |
| CORE     | 0.885         | Core industrial decision                                                   | 0.8199                | 0.7811             | 0.9936          |
| STRONG   | 0.975         | Very high confidence industrial decision                                   | 0.9020                | 0.5444             | 0.9978          |

## 7.7 Ablation result that justifies the architecture

| **Comparison**           | **Holdout ROC delta** | **Interpretation**                                                                                       |
|--------------------------|-----------------------|----------------------------------------------------------------------------------------------------------|
| FULL vs persistence-only | +0.1076               | Persistence alone is decisively insufficient.                                                            |
| FULL vs no-persistence   | +0.0014               | Thermal/spatial/land-cover already carry most discrimination; recurrence adds small complementary value. |
| FULL vs no-NTL           | -0.0003               | NTL provides no reliable benefit and worsens urban shortcut behavior.                                    |

## 7.8 Prithvi visual branch

The image branch uses the official ibm-nasa-geospatial/Prithvi-EO-2.0-300M foundation model as a frozen encoder, with a lightweight logistic-regression classifier on the resulting 1024-dimensional embedding. The pilot intentionally uses a single cloud-screened HLS scene repeated across four model frames to test spatial morphology only; it is not yet a true four-date temporal Prithvi implementation.

| **Item**                              | **Frozen pilot value**                                                               |
|---------------------------------------|--------------------------------------------------------------------------------------|
| Pilot total                           | 270 sites                                                                            |
| Usable imagery                        | 233 sites                                                                            |
| Usable DEV / HOLDOUT                  | 155 / 78                                                                             |
| Embedding dimension                   | 1024                                                                                 |
| Image size                            | 224 x 224                                                                            |
| Channels                              | 6 HLS spectral channels                                                              |
| Prithvi strong rescue threshold       | 0.965                                                                                |
| DEV OOF precision at rescue threshold | 0.9524                                                                               |
| Guarded holdout rescue                | 1 site; it was industrial                                                            |
| Policy                                | Prithvi can rescue A-Core uncertainty only; it cannot veto CORE or STRONG decisions. |

## 7.9 Learned fusion was tested and rejected for decision use

A learned logistic fusion of A-Core probability and Prithvi probability improved ranking metrics on the small usable holdout (ROC about 0.966 and PR-AUC about 0.927) but produced worse thresholded F1 because Prithvi was sometimes confidently wrong on sites where A-Core was confidently correct. The production solution therefore preserves A-Core authority and uses Prithvi only in the uncertainty band.

## 7.10 Frozen guarded decision logic

> if a_core \>= 0.975: INDUSTRIAL_CORE_STRONG  
> elif a_core \>= 0.885: INDUSTRIAL_CORE_POSITIVE  
> elif a_core \>= 0.405:  
> if HLS available and prithvi \>= 0.965: INDUSTRIAL_PRITHVI_RESCUE  
> else: UNKNOWN  
> else: NONINDUSTRIAL

## 7.11 Required Model A artifacts

| **Artifact**                                                                      | **Runtime role**                                                                                                       |
|-----------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| /content/drive/MyDrive/SIH26162/model_a_final/models/MODEL_A_FINAL.joblib         | Authoritative A-Core serialized pipeline.                                                                              |
| /content/drive/MyDrive/SIH26162/model_a_final/models/MODEL_A_PRITHVI_FINAL.joblib | Frozen target artifact for guarded image-branch head/config. Verify presence and checksum before repository packaging. |
| /content/drive/MyDrive/SIH26162/model_a_final/audit/model_a_final_config.json     | A-Core feature/threshold/config audit.                                                                                 |
| /content/drive/MyDrive/SIH26162/model_a_prithvi/results/prithvi_final_config.json | Frozen rescue-policy target config. Verify presence and checksum before repository packaging.                          |
| Prithvi_EO_V2_300M.pt + config.json + prithvi_mae.py                              | Official foundation-model weights/config/code. Pin a known repository revision for reproducible deployment.            |

# Appendix A. Exact Model A Feature Set

## T - Thermal

> mean_frp, median_frp, max_frp, std_frp, frp_cv, frp_p10, frp_p25, frp_p75, frp_p90, frp_iqr, mean_brightness, max_brightness, night_ratio

## R - Recurrence / persistence

> detections, active_days, source_lifetime_days, active_days_7, active_days_30, active_days_90, active_days_365, mean_recurrence_gap_days, median_recurrence_gap_days, std_recurrence_gap_days, detections_per_active_day

## S - Spatial

> spatial_median_m, spatial_p90_m, spatial_std_m

## L - Land cover

> tree_fraction, shrub_fraction, grass_fraction, crop_fraction, built_fraction, bare_fraction, water_fraction, wetland_fraction, mangrove_fraction

Explicitly excluded from production A-Core: persistence_seed, FIRMS type fractions/static clue, OSM distance features, and nighttime-light features.
