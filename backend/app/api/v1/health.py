"""
Health & System Statistics API Endpoints
"""

import logging
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from backend.app.db.session import get_db
from backend.app.db.models import (
    SourceSite,
    SiteModelA,
    SiteModelB,
    SiteModelC,
    SiteDailyActivity,
    Alert,
    ModelVersion
)
from backend.app.schemas.health import HealthCheck, SystemStats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthCheck, summary="Service health and database connectivity")
def get_health(db: Session = Depends(get_db)):
    """
    Returns API health, PostGIS spatial capability, and active model versions.
    """
    db_status = "connected"
    postgis_ok = False

    try:
        # Check basic connectivity
        db.execute(text("SELECT 1")).scalar()
        
        # Check PostGIS extension
        res = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'")).scalar()
        postgis_ok = bool(res)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "degraded"

    # Query active model versions
    active_models: Dict[str, str] = {}
    try:
        versions = db.query(ModelVersion).filter(ModelVersion.is_active == True).all()
        for v in versions:
            active_models[v.component] = v.version
    except Exception as e:
        logger.warning(f"Could not read model versions: {e}")
        active_models = {"STACK_DEFAULT": "2026-09-04-r1"}

    if not active_models:
        active_models = {"STACK_DEFAULT": "2026-09-04-r1"}

    return HealthCheck(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        postgis_enabled=postgis_ok,
        active_models=active_models,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/stats", response_model=SystemStats, summary="Global system metrics for command center dashboard")
def get_stats(db: Session = Depends(get_db)):
    """
    Computes global site totals, 30-day active counts, Model A/B/C breakdowns, and alert burdens.
    """
    try:
        # 1. Total sites
        total_sites = db.query(func.count(SourceSite.site_id)).scalar() or 0

        # 2. Latest activity date
        max_date = db.query(func.max(SiteDailyActivity.acq_date)).scalar()
        latest_date_str = str(max_date) if max_date else None

        # 3. Model A counts
        a_counts_raw = db.query(SiteModelA.class_name, func.count(SiteModelA.site_id)).group_by(SiteModelA.class_name).all()
        model_a_counts = {cls or "UNKNOWN": count for cls, count in a_counts_raw}
        for k in ["INDUSTRIAL", "NONINDUSTRIAL", "UNKNOWN"]:
            model_a_counts.setdefault(k, 0)

        # 4. Model B counts
        b_counts_raw = db.query(SiteModelB.state, func.count(SiteModelB.site_id)).group_by(SiteModelB.state).all()
        model_b_counts = {state or "UNKNOWN": count for state, count in b_counts_raw}
        for k in ["PERSISTENT", "DORMANT", "REACTIVATED", "INTERMITTENT", "NEW"]:
            model_b_counts.setdefault(k, 0)

        # 5. Model C counts
        c_counts_raw = db.query(SiteModelC.operational_status, func.count(SiteModelC.site_id)).group_by(SiteModelC.operational_status).all()
        model_c_counts = {status or "UNKNOWN": count for status, count in c_counts_raw}
        for k in ["NORMAL", "ELEVATED", "ANOMALOUS", "CRITICAL", "INSUFFICIENT_HISTORY"]:
            model_c_counts.setdefault(k, 0)

        # 6. Active Alerts by severity
        alert_counts_raw = (
            db.query(Alert.alert_level, func.count(Alert.alert_id))
            .filter(Alert.status == "ACTIVE")
            .group_by(Alert.alert_level)
            .all()
        )
        alert_counts = {level or "NONE": count for level, count in alert_counts_raw}
        for k in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            alert_counts.setdefault(k, 0)

        # 7. Active sites in last 30 days
        # Use Model B active_days_30 > 0 or days_since_last <= 30
        active_30d = (
            db.query(func.count(SiteModelB.site_id))
            .filter(SiteModelB.days_since_last <= 30)
            .scalar() or 0
        )

        return SystemStats(
            total_sites=total_sites,
            active_sites_30d=active_30d,
            model_a_counts=model_a_counts,
            model_b_counts=model_b_counts,
            model_c_counts=model_c_counts,
            alert_counts=alert_counts,
            latest_firms_date=latest_date_str,
            data_mode="LIVE"
        )
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate stats: {str(e)}")
