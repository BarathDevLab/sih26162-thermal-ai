---
title: 05 Validation Claims
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["10. Validation, Audits and What Can Be Claimed"]
status: authoritative
---

# 10. Validation, Audits and What Can Be Claimed

## 10.1 Model A claims

- Use the frozen geographic holdout as the primary internal performance evidence.

- The older 710-site combined external benchmark remains useful as a regression benchmark, but it is not pristine blind validation after repeated use and it belongs to the earlier A2 lineage.

- Do not present positive-context fusion tables as independent accuracy when label construction used the same GOLD/SILVER context.

## 10.2 Model B claims

- Model B is an interpretable state engine and has complete coverage of the 79,365 2025 source catalogue.

- Its validity is construct/operational validity, not supervised classification accuracy.

- The independence table against Model A demonstrates the state engine is not simply reproducing source identity.

## 10.3 Model C claims

- Chronological replay prevents future leakage.

- Severity calibration remains stable in the later replay segment.

- Controlled perturbations produce monotonic sensitivity as signal magnitude increases.

- Isolation Forest is a useful independent ranking comparator but is not ground truth.

## 10.4 Unknown / coverage caveats that the UI must surface

| **Condition**                | **Required UI behavior**                                                         |
|------------------------------|----------------------------------------------------------------------------------|
| Model A UNKNOWN              | Show Unknown / analyst review. Do not coerce to NONINDUSTRIAL.                   |
| Ground-truth UNKNOWN         | Do not present as model error. It indicates absent independent truth.            |
| Model C INSUFFICIENT_HISTORY | Show that there is no reliable site-specific baseline yet. Never display NORMAL. |
| Prithvi unavailable          | Show A-Core-only provenance; do not block the whole site.                        |
| Conflict-review source       | Show evidence conflict and suppress overconfident facility claims.               |
| No recent FIRMS event        | Show NO_RECENT_EVENT rather than a stale C anomaly label.                        |
