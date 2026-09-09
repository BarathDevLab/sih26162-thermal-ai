"""Deterministic offline demo bundle schemas."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DemoScenario(BaseModel):
    scenario_id: str
    title: str
    summary: str
    site_id: str
    start_date: str
    focal_date: str
    end_date: str
    bbox: List[float] = Field(min_length=4, max_length=4)
    limit: int = Field(ge=1, le=10000)
    expected: Dict[str, Any]
    talk_track: List[str]


class DemoScenarioCollection(BaseModel):
    schema_version: str
    model_stack_version: str
    disclaimer: str
    scenarios: List[DemoScenario]


class DemoStatus(BaseModel):
    status: str
    scenario_count: int
    cached_scenario_count: int
    expected_snapshot_count: int
    cached_snapshot_count: int
    missing_snapshots: List[str]
    invalid_snapshots: List[str]
    bundle_manifest_present: bool
