"""Network-independent deterministic demo endpoints."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.demo import DemoScenarioCollection, DemoStatus
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.services.demo_service import DemoService


router = APIRouter()


@router.get("/demo/scenarios", response_model=DemoScenarioCollection)
def get_demo_scenarios():
    return DemoService().scenarios()


@router.get("/demo/status", response_model=DemoStatus)
def get_demo_status():
    return DemoService().status()


@router.get(
    "/demo/scenarios/{scenario_id}/snapshot",
    response_model=ReplaySnapshotResponse,
)
def get_demo_snapshot(
    scenario_id: str,
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    try:
        return DemoService().snapshot(scenario_id, date)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown demo scenario: {scenario_id}")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Demo snapshot is not cached.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
