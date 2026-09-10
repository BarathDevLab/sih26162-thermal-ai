"""
SIH26162 Thermal AI FastAPI Application Entry Point
Decision Support Platform for Detection & Classification of Industrial Fires & Persistent Sources
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from backend.app.db.session import engine, is_postgis_available, SessionLocal
from backend.app.api.v1.router import api_v1_router
from backend.app.services.stack_readiness import run_stack_preflight, get_last_readiness_report

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sih26162.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for connection pool warmup and graceful shutdown.
    """
    logger.info("Initializing SIH26162 Thermal AI Platform...")
    database_connected = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_connected = True
        postgis_ok = is_postgis_available(engine)
        logger.info(
            f"Database connected successfully ({engine.url.drivername}). "
            f"PostGIS available: {postgis_ok}"
        )
    except Exception as e:
        logger.warning(f"Database pre-flight connection check failed: {e}")

    if database_connected:
        db = SessionLocal()
        try:
            readiness = run_stack_preflight(db)
            app.state.stack_readiness = readiness.to_dict()
            logger.info("Runtime readiness: %s (%s)", readiness.status, readiness.detail)
            if readiness.can_start_live:
                logger.info(
                    "Stable source-member spatial index will load lazily on the first "
                    "FIRMS ingestion batch."
                )
        finally:
            db.close()
    else:
        readiness = get_last_readiness_report()
        app.state.stack_readiness = readiness.to_dict()

    # Live jobs are gated by the common current stack snapshot.
    if readiness.can_start_live:
        try:
            from backend.app.services.scheduler import start_scheduler
            start_scheduler()
        except Exception as e:
            logger.warning(f"Failed to start APScheduler in lifespan: {e}")
    else:
        from backend.app.services.startup_catchup import (
            should_start_startup_catchup,
            start_startup_catchup,
        )

        if should_start_startup_catchup(readiness):
            app.state.startup_catchup_task = start_startup_catchup(app)
        elif readiness.status == "STALE_BACKFILL":
            logger.warning(
                "Automatic startup catch-up was not started. Confirm FIRMS_MAP_KEY is set "
                "and AUTO_STARTUP_CATCHUP is not false."
            )

    yield

    logger.info("Shutting down SIH26162 Thermal AI Platform...")
    try:
        from backend.app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"Failed to stop scheduler: {e}")

    engine.dispose()
    logger.info("Database connection pool disposed.")


app = FastAPI(
    title="SIH26162 Thermal AI Decision Support Platform",
    description=(
        "Production API service for AI-based detection, classification, and continuous "
        "monitoring of industrial fires and persistent thermal sources across India. "
        "Integrates Model A (XGBoost + Prithvi visual rescue), Model B (temporal persistence), "
        "Model C (site-specific anomaly engine), and deterministic decision alert routing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# Viewport GeoJSON is the largest routine response. Compress it before it
# crosses the Vite/nginx boundary while keeping tiny control responses cheap.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

# CORS configuration for OSIRIS web command center
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
custom_origins = os.environ.get("ALLOWED_ORIGINS")
if custom_origins:
    origins.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", summary="Root Platform Information")
def root_info() -> Dict[str, Any]:
    """
    Root status endpoint providing documentation pointers and service identification.
    """
    return {
        "service": "SIH26162 Thermal AI Decision Support Platform",
        "version": "1.0.0",
        "status": get_last_readiness_report().status,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_v1_prefix": "/api/v1"
    }
