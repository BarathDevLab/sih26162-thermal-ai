---
title: 04 Model C
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["9. Model C - Thermal Anomaly"]
status: authoritative
---

# 9. Model C - Thermal Anomaly

<img src="assets/model_c.png" style="width:6.7in;height:3.58526in" />

## 9.1 Technical type

Model C V3 is an unsupervised, site-specific statistical time-series anomaly detector. It learns a baseline from each site's earlier active days and measures whether the current active-day behavior is unusual. Isolation Forest is retained only as a classical unsupervised-ML ablation and secondary audit.

## 9.2 Cold-start requirements

| **Parameter**      | **Frozen value** | **Meaning**                                                                    |
|--------------------|------------------|--------------------------------------------------------------------------------|
| MIN_ACTIVE_HISTORY | 5                | At least five prior active days before scoring current day.                    |
| MIN_SPAN_DAYS      | 30               | Prior history must span at least 30 days.                                      |
| MIN_GAP_HISTORY    | 3                | At least three historical recurrence gaps before recurrence-burst score.       |
| EWMA_ALPHA         | 0.35             | Weight of current change signal.                                               |
| CUSUM_K            | 2.0              | CUSUM reference / drift allowance.                                             |
| CUSUM_CAP          | 50               | Bound cumulative change.                                                       |
| CHANGE_RESET_GAP   | 30 days          | Reset EWMA/CUSUM after long inactivity so C does not duplicate B reactivation. |
| Z_CAP              | 20               | Cap robust component z-scores.                                                 |

## 9.3 Robust baseline

> location = median(history)  
> scale = 1.4826 \* median(\|x - median\|)  
> if scale ~ 0: scale = IQR / 1.349  
> scale floor = max(scale, 0.05 \* \|median\|, 1e-3)

## 9.4 Four frozen anomaly groups

| **Group**        | **Raw signal**                                                   | **Direction**                                                                          |
|------------------|------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Intensity        | max(z_max_frp, z_mean_frp)                                       | Only positive thermal escalation matters.                                              |
| Density          | z of log1p(detections/day)                                       | Unexpectedly many detections in the active day.                                        |
| Recurrence burst | max(0, (historical_median_gap - current_gap) / robust_gap_scale) | Only unexpectedly SHORT return gaps are anomalous; long inactivity belongs to Model B. |
| Change           | max(EWMA score, bounded CUSUM score)                             | Sustained escalation; reset after \>30 d gap.                                          |

## 9.5 Chronological replay

For each site-day at time t, the baseline is calculated only from active days strictly before t. The current day is then scored. In live mode, multiple new FIRMS detections on the same date update the current day aggregate in place; the baseline continues to exclude the current day until the day is complete and becomes historical on the next date.

## 9.6 V3 calibration and score

1.  Convert each anomaly group to an empirical midrank percentile using the earlier calibration replay.

2.  Take the two strongest available group percentiles and average them. This requires corroboration and prevents one isolated axis from creating CRITICAL.

3.  Calibrate that top-two composite again to a final empirical midrank percentile.

4.  Apply frozen severity bands.

| **Status**           | **Final score**                                                                                          |
|----------------------|----------------------------------------------------------------------------------------------------------|
| NORMAL               | \< 0.950                                                                                                 |
| ELEVATED             | 0.950 to \<0.990                                                                                         |
| ANOMALOUS            | 0.990 to \<0.999                                                                                         |
| CRITICAL             | \>=0.999                                                                                                 |
| INSUFFICIENT_HISTORY | Cold start: site history does not satisfy scoring prerequisites.                                         |
| NO_RECENT_EVENT      | Operational presentation status when the site has had no detection within 30 days; not an anomaly class. |

## 9.7 V3 validation behavior

| **Audit**                            | **Result**                                                                                               |
|--------------------------------------|----------------------------------------------------------------------------------------------------------|
| All replay event levels              | 235,866 insufficient; 58,822 normal; 2,210 elevated; 394 anomalous; 56 critical.                         |
| Later replay stability               | 25,408 normal; 774 elevated; 118 anomalous; 9 critical.                                                  |
| Current recent sites                 | 9,010                                                                                                    |
| Current recent scoreable sites       | 2,267 (25.2%)                                                                                            |
| Current operational status           | 2,174 normal; 76 elevated; 15 anomalous; 2 critical; 6,743 insufficient history; 70,355 no recent event. |
| Isolation Forest rank correlation    | Spearman ~0.9507 with production C score.                                                                |
| Top 1% overlap with Isolation Forest | 382 / 614 = 62.2%.                                                                                       |
| x2 perturbation                      | 94.85% scores increased; 17.1% \>= elevated; 2.15% \>= anomalous; 0.15% \>= critical.                    |
| x3 perturbation                      | 98.95% scores increased; 34.0% \>= elevated; 6.85% \>= anomalous; 0.95% \>= critical.                    |
| x5 perturbation                      | 99.55% scores increased; 63.5% \>= elevated; 18.0% \>= anomalous; 4.35% \>= critical.                    |

## 9.8 What Model C can and cannot claim

| **Valid claim** The detector is chronologically leakage-free, stable across later replay, responsive monotonically to controlled thermal/density perturbations, and broadly agrees with an independent Isolation Forest ranking audit. |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

| **Invalid claim** Do not report Model C accuracy, precision, recall or industrial-fire detection rate until independent anomaly ground truth is collected. Controlled perturbation is a sensitivity test, not event-level ground truth. |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## 9.9 Deployment artifacts

| **Artifact**                                                                          | **Runtime role**                                                                                                                                        |
|---------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| /content/drive/MyDrive/SIH26162/model_c/models/MODEL_C_V3_FROZEN.joblib               | Frozen V3 calibration target artifact (config + group_reference + final_reference). Generate/verify from the freeze cell and checksum before packaging. |
| /content/drive/MyDrive/SIH26162/model_c/built/MODEL_C_EVENT_REPLAY_V3.parquet         | Chronological replay archive.                                                                                                                           |
| /content/drive/MyDrive/SIH26162/model_c/built/MODEL_C_V3_LATEST_SITE_STATUS_FINAL.csv | Target latest-site snapshot generated by final export cell; verify/create before packaging. It becomes stale after 2026 backfill.                       |
| /content/drive/MyDrive/SIH26162/model_c/results/MODEL_C_V3_RECENT_ALERTS.csv          | Target ELEVATED/ANOMALOUS/CRITICAL export generated by final export cell; verify/create before packaging.                                               |
| /content/drive/MyDrive/SIH26162/model_c/audit/MODEL_C_V3_FROZEN.json                  | Frozen V3 config target file; verify/create and checksum before packaging.                                                                              |
| backend/engines/model_c.py                                                            | TO IMPLEMENT. Online scoring engine that reproduces notebook logic exactly.                                                                             |
