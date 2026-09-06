"""
Unified API v1 Router Definition
"""

from fastapi import APIRouter

from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.sites import router as sites_router
from backend.app.api.v1.timeline import router as timeline_router
from backend.app.api.v1.evidence import router as evidence_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.layers import router as layers_router
from backend.app.api.v1.replay import router as replay_router
from backend.app.api.v1.stream import router as stream_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, tags=["Health & Diagnostics"])
api_v1_router.include_router(sites_router, tags=["Source Sites"])
api_v1_router.include_router(timeline_router, tags=["Site Timeline & Detections"])
api_v1_router.include_router(evidence_router, tags=["Facility Evidence & Imagery"])
api_v1_router.include_router(alerts_router, tags=["Operational Alerts"])
api_v1_router.include_router(layers_router, tags=["Map Layers"])
api_v1_router.include_router(replay_router, tags=["Historical Replay"])
api_v1_router.include_router(stream_router, tags=["Live Alert Stream"])
