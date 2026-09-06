"""
Server-Sent Events (SSE) Alert Stream Endpoint
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from backend.app.db.session import SessionLocal
from backend.app.db.models import Alert, SourceSite, SiteModelA

logger = logging.getLogger(__name__)

router = APIRouter()


async def alert_event_generator(
    request: Request,
    severity: Optional[str] = None,
    poll_interval: float = 5.0,
    limit: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Yields SSE formatted events for operational alerts and heartbeats.
    Format:
        event: <event_name>
        data: <json_payload>

    """
    event_count = 0

    # 1. Yield initial connected event
    initial_payload = {
        "event": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Connected to SIH26162 Operational Alert Stream"
    }
    yield f"event: connected\ndata: {json.dumps(initial_payload)}\n\n"
    event_count += 1
    if limit is not None and event_count >= limit:
        return

    last_seen_updated_at: Optional[datetime] = None

    # 2. Stream loop
    while True:
        if await request.is_disconnected():
            logger.info("SSE client disconnected.")
            break

        try:
            # Query recent active alerts in short-lived session
            with SessionLocal() as db:
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
                        Alert.updated_at,
                        SourceSite.latitude,
                        SourceSite.longitude,
                        SiteModelA.class_name.label("a_class")
                    )
                    .join(SourceSite, Alert.site_id == SourceSite.site_id)
                    .outerjoin(SiteModelA, Alert.site_id == SiteModelA.site_id)
                    .filter(Alert.status == "ACTIVE")
                )

                if severity:
                    query = query.filter(Alert.alert_level == severity.upper())

                if last_seen_updated_at:
                    query = query.filter(Alert.updated_at > last_seen_updated_at)
                    alerts = query.order_by(Alert.updated_at.asc()).limit(50).all()
                else:
                    # Initial batch of latest 5 critical/high alerts
                    alerts = query.order_by(Alert.updated_at.desc()).limit(5).all()
                    alerts = list(reversed(alerts))

                for r in alerts:
                    if r.updated_at and (last_seen_updated_at is None or r.updated_at > last_seen_updated_at):
                        last_seen_updated_at = r.updated_at

                    alert_payload = {
                        "alert_id": r.alert_id,
                        "site_id": r.site_id,
                        "site_day": str(r.site_day),
                        "alert_type": r.alert_type,
                        "alert_level": r.alert_level,
                        "headline": r.headline,
                        "reason_codes": r.reason_codes or [],
                        "evidence_required": bool(r.evidence_required),
                        "fingerprint": r.fingerprint,
                        "status": r.status,
                        "is_escalation": bool(r.is_escalation),
                        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                        "latitude": float(r.latitude) if r.latitude is not None else None,
                        "longitude": float(r.longitude) if r.longitude is not None else None,
                        "a_class": r.a_class or "UNKNOWN"
                    }
                    yield f"event: alert\ndata: {json.dumps(alert_payload)}\n\n"
                    event_count += 1
                    if limit is not None and event_count >= limit:
                        return

        except Exception as e:
            logger.error(f"Error checking alerts in SSE generator: {e}")

        # Yield ping heartbeat
        ping_payload = {
            "type": "ping",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        yield f"event: ping\ndata: {json.dumps(ping_payload)}\n\n"
        event_count += 1
        if limit is not None and event_count >= limit:
            return

        await asyncio.sleep(poll_interval)


@router.get(
    "/stream/alerts",
    summary="Server-Sent Events stream for operational alerts and live updates"
)
async def stream_alerts(
    request: Request,
    severity: Optional[str] = Query(None, description="Filter stream by severity: CRITICAL, HIGH, etc."),
    poll_interval: float = Query(5.0, ge=1.0, le=60.0, description="Polling interval in seconds"),
    limit: Optional[int] = Query(None, ge=1, description="Max events to yield before closing connection")
):
    """
    Subscribes to live operational alerts via Server-Sent Events (SSE).
    Emits an initial `connected` event, followed by `alert` events and periodic `ping` heartbeats.
    """
    return StreamingResponse(
        alert_event_generator(request, severity=severity, poll_interval=poll_interval, limit=limit),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
