"""
Operational Alerts API Endpoints
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Alert, SourceSite, SiteModelA
from backend.app.schemas.alerts import (
    AlertFeedResponse,
    AlertItem,
    AlertAckRequest,
    AlertAckResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/alerts",
    response_model=AlertFeedResponse,
    summary="Active operational alert feed with severity and status filters"
)
def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW, INFO"),
    alert_type: Optional[str] = Query(None, description="Filter by classification type (e.g. CRITICAL_INDUSTRIAL_ANOMALY)"),
    site_id: Optional[str] = Query(None, description="Filter by target source site ID"),
    status: Optional[str] = Query("ACTIVE", description="Filter by status: ACTIVE, ACKNOWLEDGED, ALL"),
    limit: int = Query(100, ge=1, le=1000, description="Max alerts to return"),
    db: Session = Depends(get_db)
):
    """
    Returns prioritized operational alerts enriched with site coordinates and Model A classification.
    """
    try:
        query = (
            db.query(
                Alert.alert_id,
                Alert.site_id,
                Alert.site_day,
                Alert.alert_type,
                Alert.alert_level,
                Alert.headline,
                Alert.reason_codes,
                Alert.evidence_required,
                Alert.fingerprint,
                Alert.status,
                Alert.is_escalation,
                Alert.created_at,
                Alert.updated_at,
                SourceSite.latitude,
                SourceSite.longitude,
                SiteModelA.class_name.label("a_class")
            )
            .join(SourceSite, Alert.site_id == SourceSite.site_id)
            .outerjoin(SiteModelA, Alert.site_id == SiteModelA.site_id)
        )

        if status and status.upper() != "ALL":
            query = query.filter(Alert.status == status.upper())

        if severity:
            query = query.filter(Alert.alert_level == severity.upper())

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        if site_id:
            query = query.filter(Alert.site_id == site_id)

        rows = query.order_by(Alert.updated_at.desc()).limit(limit).all()

        items: List[AlertItem] = []
        for r in rows:
            items.append(
                AlertItem(
                    alert_id=r.alert_id,
                    site_id=r.site_id,
                    site_day=str(r.site_day),
                    alert_type=r.alert_type,
                    alert_level=r.alert_level,
                    headline=r.headline,
                    reason_codes=r.reason_codes if isinstance(r.reason_codes, list) else [],
                    evidence_required=bool(r.evidence_required),
                    fingerprint=r.fingerprint,
                    status=r.status,
                    is_escalation=bool(r.is_escalation),
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    updated_at=r.updated_at.isoformat() if r.updated_at else "",
                    latitude=float(r.latitude) if r.latitude is not None else None,
                    longitude=float(r.longitude) if r.longitude is not None else None,
                    a_class=r.a_class or "UNKNOWN"
                )
            )

        return AlertFeedResponse(
            total_alerts=len(items),
            alerts=items
        )
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")


@router.post(
    "/alerts/{alert_id}/ack",
    response_model=AlertAckResponse,
    summary="Acknowledge an operational alert"
)
def acknowledge_alert(
    alert_id: str,
    req: AlertAckRequest,
    db: Session = Depends(get_db)
):
    """
    Records analyst acknowledgement and triage timestamp for an active alert.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = req.acknowledged_by
    alert.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    return AlertAckResponse(
        alert_id=alert.alert_id,
        status=alert.status,
        acknowledged_by=alert.acknowledged_by or req.acknowledged_by,
        updated_at=alert.updated_at.isoformat() if alert.updated_at else "",
        message=f"Alert {alert_id} acknowledged by {req.acknowledged_by}."
    )
