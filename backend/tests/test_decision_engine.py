"""
Tests for Unified Decision & Alert Engine
Verifies all 10 alert taxonomy rules, severity ranking, same-day incident escalation,
and deduplication fingerprint stability.
"""

import pytest
from datetime import datetime, timezone
from backend.app.engines.decision_engine import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()


def test_critical_industrial_anomaly(engine):
    res = engine.evaluate(
        site_id="SITE_001",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG", "p_core": 0.98},
        model_b_result={"state": "PERSISTENT", "confidence": "HIGH"},
        model_c_result={"status": "CRITICAL", "c_score": 0.9995}
    )
    assert res["alert_type"] == "CRITICAL_INDUSTRIAL_ANOMALY"
    assert res["alert_level"] == "CRITICAL"
    assert res["evidence_required"] is True
    assert res["is_escalation"] is False


def test_high_industrial_anomaly(engine):
    res = engine.evaluate(
        site_id="SITE_002",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_POSITIVE", "p_core": 0.92},
        model_b_result={"state": "PERSISTENT", "confidence": "HIGH"},
        model_c_result={"status": "ANOMALOUS", "c_score": 0.992}
    )
    assert res["alert_type"] == "HIGH_INDUSTRIAL_ANOMALY"
    assert res["alert_level"] == "HIGH"
    assert res["evidence_required"] is True


def test_industrial_reactivation_anomaly(engine):
    res = engine.evaluate(
        site_id="SITE_003",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG", "p_core": 0.99},
        model_b_result={"state": "REACTIVATED", "confidence": "HIGH"},
        model_c_result={"status": "ELEVATED", "c_score": 0.96}
    )
    assert res["alert_type"] == "INDUSTRIAL_REACTIVATION_ANOMALY"
    assert res["alert_level"] == "HIGH"
    assert res["evidence_required"] is True


def test_industrial_elevation(engine):
    res = engine.evaluate(
        site_id="SITE_004",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_PRITHVI_RESCUE", "p_core": 0.75, "p_prithvi": 0.97},
        model_b_result={"state": "INTERMITTENT", "confidence": "MEDIUM"},
        model_c_result={"status": "ELEVATED", "c_score": 0.955}
    )
    assert res["alert_type"] == "INDUSTRIAL_ELEVATION"
    assert res["alert_level"] == "MEDIUM"
    assert res["evidence_required"] is False


def test_unknown_critical_review(engine):
    # CRITICAL rule: Unknown sources must NEVER be called industrial
    res = engine.evaluate(
        site_id="SITE_005",
        site_day="2026-03-01",
        model_a_result={"decision": "UNKNOWN", "p_core": 0.55},
        model_b_result={"state": "NEW", "confidence": "LOW"},
        model_c_result={"status": "CRITICAL", "c_score": 0.9992}
    )
    assert res["alert_type"] == "UNKNOWN_CRITICAL_REVIEW"
    assert res["alert_level"] == "HIGH"
    assert res["evidence_required"] is True
    assert "industrial" not in res["headline"].lower()


def test_unknown_anomaly_review(engine):
    res = engine.evaluate(
        site_id="SITE_006",
        site_day="2026-03-01",
        model_a_result={"decision": "UNKNOWN", "p_core": 0.60},
        model_b_result={"state": "DORMANT", "confidence": "HIGH"},
        model_c_result={"status": "ANOMALOUS", "c_score": 0.991}
    )
    assert res["alert_type"] == "UNKNOWN_ANOMALY_REVIEW"
    assert res["alert_level"] == "MEDIUM"
    assert res["evidence_required"] is True


def test_new_source_review(engine):
    res = engine.evaluate(
        site_id="SITE_007",
        site_day="2026-03-01",
        model_a_result={"decision": "UNKNOWN", "p_core": 0.50},
        model_b_result={"state": "NEW", "confidence": "HIGH"},
        model_c_result={"status": "INSUFFICIENT_HISTORY", "c_score": None}
    )
    assert res["alert_type"] == "NEW_SOURCE_REVIEW"
    assert res["alert_level"] == "MEDIUM"
    assert res["evidence_required"] is True


def test_normal_industrial_operation(engine):
    res = engine.evaluate(
        site_id="SITE_008",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG", "p_core": 0.99},
        model_b_result={"state": "PERSISTENT", "confidence": "HIGH"},
        model_c_result={"status": "NORMAL", "c_score": 0.45}
    )
    assert res["alert_type"] == "NORMAL_INDUSTRIAL_OPERATION"
    assert res["alert_level"] == "INFO"
    assert res["evidence_required"] is False


def test_nonindustrial_activity(engine):
    res = engine.evaluate(
        site_id="SITE_009",
        site_day="2026-03-01",
        model_a_result={"decision": "NONINDUSTRIAL", "p_core": 0.12},
        model_b_result={"state": "INTERMITTENT", "confidence": "LOW"},
        model_c_result={"status": "CRITICAL", "c_score": 0.999}
    )
    assert res["alert_type"] == "NONINDUSTRIAL_ACTIVITY"
    assert res["alert_level"] == "LOW"
    assert res["evidence_required"] is False


def test_no_alert(engine):
    res = engine.evaluate(
        site_id="SITE_010",
        site_day="2026-03-01",
        model_a_result={"decision": "UNKNOWN", "p_core": 0.50},
        model_b_result={"state": "DORMANT", "confidence": "HIGH"},
        model_c_result={"status": "NO_RECENT_EVENT", "c_score": None}
    )
    assert res["alert_type"] == "NO_ALERT"
    assert res["alert_level"] == "NONE"


def test_same_day_incident_escalation(engine):
    # Morning satellite pass: ELEVATED (MEDIUM)
    t1 = datetime(2026, 3, 1, 8, 30, tzinfo=timezone.utc)
    first_alert = engine.evaluate(
        site_id="SITE_ESC_1",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG"},
        model_b_result={"state": "PERSISTENT"},
        model_c_result={"status": "ELEVATED"},
        as_of_time=t1
    )
    assert first_alert["alert_type"] == "INDUSTRIAL_ELEVATION"
    assert first_alert["alert_level"] == "MEDIUM"
    assert first_alert["is_escalation"] is False

    # Afternoon satellite pass: Thermal surge -> CRITICAL (CRITICAL)
    t2 = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)
    escalated_alert = engine.evaluate(
        site_id="SITE_ESC_1",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG"},
        model_b_result={"state": "PERSISTENT"},
        model_c_result={"status": "CRITICAL"},
        existing_alert=first_alert,
        as_of_time=t2
    )

    assert escalated_alert["alert_type"] == "CRITICAL_INDUSTRIAL_ANOMALY"
    assert escalated_alert["alert_level"] == "CRITICAL"
    assert escalated_alert["is_escalation"] is True
    assert escalated_alert["previous_alert_level"] == "MEDIUM"
    assert escalated_alert["previous_alert_type"] == "INDUSTRIAL_ELEVATION"
    assert escalated_alert["created_at"] == first_alert["created_at"]
    assert escalated_alert["updated_at"] == t2.isoformat()


def test_no_downgrade_on_same_day(engine):
    # Existing CRITICAL alert
    critical_alert = engine.evaluate(
        site_id="SITE_ESC_2",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG"},
        model_b_result={"state": "PERSISTENT"},
        model_c_result={"status": "CRITICAL"}
    )

    # Later lower-intensity pass evaluates to NORMAL (INFO)
    subsequent = engine.evaluate(
        site_id="SITE_ESC_2",
        site_day="2026-03-01",
        model_a_result={"decision": "INDUSTRIAL_CORE_STRONG"},
        model_b_result={"state": "PERSISTENT"},
        model_c_result={"status": "NORMAL"},
        existing_alert=critical_alert
    )

    # Should retain CRITICAL status without downgrading
    assert subsequent["alert_level"] == "CRITICAL"
    assert subsequent["alert_type"] == "CRITICAL_INDUSTRIAL_ANOMALY"


def test_fingerprint_stability(engine):
    fp1 = engine.compute_fingerprint("SITE_X", "2026-03-01", "CRITICAL_INDUSTRIAL_ANOMALY", "v1.0")
    fp2 = engine.compute_fingerprint("SITE_X", "2026-03-01", "CRITICAL_INDUSTRIAL_ANOMALY", "v1.0")
    assert fp1 == fp2

    fp3 = engine.compute_fingerprint("SITE_Y", "2026-03-01", "CRITICAL_INDUSTRIAL_ANOMALY", "v1.0")
    assert fp1 != fp3
