"""
Unified Decision & Alert Engine
Synthesizes Model A (identity), Model B (temporal state), and Model C (statistical anomaly)
into operational alert classifications with deterministic deduplication and same-day escalation.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

DEFAULT_STACK_VERSION = "2026-09-04-r1"

SEVERITY_ORDER = [
    "NONE",
    "INFO",
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL"
]

SEVERITY_RANK = {level: idx for idx, level in enumerate(SEVERITY_ORDER)}


class DecisionEngine:
    """
    Deterministic A+B+C Fusion and Operational Alert Engine.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        model_stack_version: str = DEFAULT_STACK_VERSION
    ):
        self.model_stack_version = model_stack_version
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        Loads decision engine rules and severity specification.
        Falls back to frozen or draft config if path not specified.
        """
        candidate_paths = [
            config_path,
            os.path.join("backend", "config", "decision_engine.json"),
            os.path.join("backend", "config", "decision_engine_draft.json")
        ]

        for p in candidate_paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    logger.info(f"Loaded decision engine config from {p}")
                    return cfg
                except Exception as e:
                    logger.warning(f"Failed to read {p}: {e}")

        logger.info("Using embedded default decision engine specification.")
        return {}

    @staticmethod
    def is_industrial(model_a_decision: str) -> bool:
        """
        Returns True if Model A classified the source as Industrial.
        """
        d = str(model_a_decision).strip().upper()
        return d in (
            "INDUSTRIAL_CORE_STRONG",
            "INDUSTRIAL_CORE_POSITIVE",
            "INDUSTRIAL_PRITHVI_RESCUE"
        ) or d.startswith("INDUSTRIAL_")

    @staticmethod
    def is_unknown(model_a_decision: str) -> bool:
        """
        Returns True if Model A classified the source as Unknown.
        """
        return str(model_a_decision).strip().upper() == "UNKNOWN"

    @staticmethod
    def is_nonindustrial(model_a_decision: str) -> bool:
        """
        Returns True if Model A classified the source as Nonindustrial.
        """
        return str(model_a_decision).strip().upper() == "NONINDUSTRIAL"

    def compute_fingerprint(
        self,
        site_id: str,
        site_day: str,
        alert_type: str,
        stack_version: Optional[str] = None
    ) -> str:
        """
        Generates deterministic SHA-256 fingerprint for deduplication.
        Key elements: site_id + site_day + alert_type + model_stack_version.
        """
        version = stack_version or self.model_stack_version
        raw_key = f"{site_id}_{site_day}_{alert_type}_{version}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def evaluate(
        self,
        site_id: str,
        site_day: str,
        model_a_result: Dict[str, Any],
        model_b_result: Dict[str, Any],
        model_c_result: Dict[str, Any],
        existing_alert: Optional[Dict[str, Any]] = None,
        as_of_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Fuses Model A, B, and C outputs to generate an operational alert.
        Handles same-day incident escalation if existing_alert is provided.
        """
        now_iso = (as_of_time or datetime.now(timezone.utc)).isoformat()
        
        # Extract standardized outputs
        a_dec = str(model_a_result.get("decision", "")).strip().upper()
        b_state = str(model_b_result.get("state", "")).strip().upper()
        c_status = str(model_c_result.get("status", model_c_result.get("model_c_level", ""))).strip().upper()

        is_ind = self.is_industrial(a_dec)
        is_unk = self.is_unknown(a_dec)
        is_non_ind = self.is_nonindustrial(a_dec)

        # Rule evaluation in precedence order
        alert_type = "NO_ALERT"
        alert_level = "NONE"
        headline = "Normal background; no qualifying alert."
        evidence_required = False
        reason_codes = [f"A={a_dec}", f"B={b_state}", f"C={c_status}"]

        # 1. Critical Industrial Anomaly
        if is_ind and c_status == "CRITICAL":
            alert_type = "CRITICAL_INDUSTRIAL_ANOMALY"
            alert_level = "CRITICAL"
            headline = "Critical thermal anomaly detected at industrial facility"
            evidence_required = True

        # 2. Industrial Reactivation Anomaly (specific context over generic anomaly)
        elif is_ind and b_state == "REACTIVATED" and c_status in ("ELEVATED", "ANOMALOUS"):
            alert_type = "INDUSTRIAL_REACTIVATION_ANOMALY"
            alert_level = "HIGH"
            headline = "Industrial site thermally abnormal after extended dormancy"
            evidence_required = True

        # 3. High Industrial Anomaly
        elif is_ind and c_status == "ANOMALOUS":
            alert_type = "HIGH_INDUSTRIAL_ANOMALY"
            alert_level = "HIGH"
            headline = "Significant thermal anomaly detected at industrial facility"
            evidence_required = True

        # 4. Unknown Critical Review (Must not be called industrial)
        elif is_unk and c_status == "CRITICAL":
            alert_type = "UNKNOWN_CRITICAL_REVIEW"
            alert_level = "HIGH"
            headline = "Urgent analyst review required: critical thermal anomaly at unclassified source"
            evidence_required = True

        # 5. Unknown Anomaly Review
        elif is_unk and c_status in ("ELEVATED", "ANOMALOUS"):
            alert_type = "UNKNOWN_ANOMALY_REVIEW"
            alert_level = "MEDIUM"
            headline = "Unclassified thermal source exhibiting anomalous behavior"
            evidence_required = True

        # 6. Industrial Elevation
        elif is_ind and c_status == "ELEVATED":
            alert_type = "INDUSTRIAL_ELEVATION"
            alert_level = "MEDIUM"
            headline = "Elevated thermal activity observed at industrial site"
            evidence_required = False

        # 7. New Source Review
        elif b_state == "NEW" and (is_unk or is_ind) and c_status == "INSUFFICIENT_HISTORY":
            alert_type = "NEW_SOURCE_REVIEW"
            alert_level = "MEDIUM"
            headline = "New thermal source identified; awaiting baseline accumulation"
            evidence_required = True

        # 8. Normal Industrial Operation
        elif is_ind and c_status == "NORMAL":
            alert_type = "NORMAL_INDUSTRIAL_OPERATION"
            alert_level = "INFO"
            headline = "Industrial facility operating within expected thermal baseline"
            evidence_required = False

        # 9. Non-industrial Activity
        elif is_non_ind:
            alert_type = "NONINDUSTRIAL_ACTIVITY"
            alert_level = "LOW"
            headline = "Non-industrial thermal activity detected"
            evidence_required = False

        # 10. Default No Alert
        else:
            alert_type = "NO_ALERT"
            alert_level = "NONE"
            headline = "Thermal observations consistent with background activity"
            evidence_required = False

        fingerprint = self.compute_fingerprint(
            site_id=site_id,
            site_day=site_day,
            alert_type=alert_type,
            stack_version=self.model_stack_version
        )

        # Handle Same-Day Escalation
        is_escalation = False
        created_at = now_iso
        updated_at = now_iso
        previous_alert_type = None
        previous_alert_level = None

        if existing_alert is not None:
            old_level = existing_alert.get("alert_level", "NONE")
            old_rank = SEVERITY_RANK.get(old_level, 0)
            new_rank = SEVERITY_RANK.get(alert_level, 0)

            if new_rank > old_rank:
                # Escalate
                is_escalation = True
                created_at = existing_alert.get("created_at", now_iso)
                updated_at = now_iso
                previous_alert_type = existing_alert.get("alert_type")
                previous_alert_level = old_level
                headline = f"{headline} (Escalated from {previous_alert_level})"
                reason_codes.append(f"ESCALATED_FROM_{previous_alert_level}")
            else:
                # Do not downgrade same-day alert
                return existing_alert

        return {
            "site_id": site_id,
            "site_day": site_day,
            "alert_level": alert_level,
            "alert_type": alert_type,
            "headline": headline,
            "reason_codes": reason_codes,
            "evidence_required": evidence_required,
            "is_escalation": is_escalation,
            "previous_alert_type": previous_alert_type,
            "previous_alert_level": previous_alert_level,
            "created_at": created_at,
            "updated_at": updated_at,
            "model_stack_version": self.model_stack_version,
            "alert_fingerprint": fingerprint
        }
