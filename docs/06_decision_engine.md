---
title: 06 Decision Engine
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["11. Unified Decision / Alert Engine - To Implement"]
status: draft-policy
---

# 11. Unified Decision / Alert Engine - To Implement

The decision engine is not a fourth ML model. It is a deterministic policy layer that combines identity, state and anomaly outputs into an operational alert type, severity, reason and evidence package. This layer should be coded, regression-tested and then frozen before the frontend is considered complete.

## 11.1 Proposed initial alert taxonomy

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Alert type</strong></th>
<th><strong>Suggested severity</strong></th>
<th><strong>Condition</strong></th>
<th><strong>Meaning</strong></th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>CRITICAL_INDUSTRIAL_ANOMALY</td>
<td>CRITICAL</td>
<td>A industrial AND C critical</td>
<td>High-confidence industrial source with extreme site-relative anomaly.</td>
</tr>
<tr class="even">
<td>HIGH_INDUSTRIAL_ANOMALY</td>
<td>HIGH</td>
<td>A industrial AND C anomalous</td>
<td>Industrial source with strong abnormal behavior.</td>
</tr>
<tr class="odd">
<td>INDUSTRIAL_REACTIVATION_<br />
ANOMALY</td>
<td>HIGH</td>
<td>A industrial AND B reactivated AND C elevated/anomalous</td>
<td>Industrial source has returned after dormancy and is thermally unusual.</td>
</tr>
<tr class="even">
<td>INDUSTRIAL_ELEVATION</td>
<td>MEDIUM</td>
<td>A industrial AND C elevated</td>
<td>Moderate abnormality requiring watch / evidence review.</td>
</tr>
<tr class="odd">
<td>UNKNOWN_CRITICAL_REVIEW</td>
<td>HIGH</td>
<td>A unknown AND C critical</td>
<td>Do not call it industrial; urgent analyst classification required.</td>
</tr>
<tr class="even">
<td>UNKNOWN_ANOMALY_REVIEW</td>
<td>MEDIUM</td>
<td>A unknown AND C elevated/anomalous</td>
<td>Unclassified source with abnormal behavior.</td>
</tr>
<tr class="odd">
<td>NEW_SOURCE_REVIEW</td>
<td>MEDIUM</td>
<td>B new AND A unknown/industrial AND C insufficient</td>
<td>New thermal source; anomaly baseline not yet available.</td>
</tr>
<tr class="even">
<td>NORMAL_INDUSTRIAL_OPERATION</td>
<td>INFO</td>
<td>A industrial AND C normal</td>
<td>Industrial source currently within learned thermal behavior.</td>
</tr>
<tr class="odd">
<td>NONINDUSTRIAL_ACTIVITY</td>
<td>LOW/INFO</td>
<td>A nonindustrial</td>
<td>Retain temporal/anomaly info but do not frame as industrial incident.</td>
</tr>
<tr class="even">
<td>NO_ALERT</td>
<td>NONE</td>
<td>No qualifying rule</td>
<td>Normal background / no recent event.</td>
</tr>
</tbody>
</table>

| **Not frozen yet** The table above is the recommended starting policy, not a finished model result. Implement it in decision_engine.py, run regression examples across all A/B/C combinations, review false-alert burden, then write a versioned decision_engine.json. |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## 11.2 Output contract

- alert_level: NONE / INFO / LOW / MEDIUM / HIGH / CRITICAL

- alert_type: stable machine-readable enum

- headline: short human-readable message

- reason_codes: list of exact A/B/C conditions

- evidence_required: whether analyst imagery/context should be loaded

- created_at, updated_at, model_stack_version, alert_fingerprint

## 11.3 Alert deduplication

Use an alert fingerprint such as site_id + site-day + alert_type + model_stack_version. If a site progresses ELEVATED -\> ANOMALOUS -\> CRITICAL on the same active day, update/escalate the existing incident instead of generating three unrelated notifications.
