"""Incremental 750 m member-point source resolver."""

from __future__ import annotations

import math
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.neighbors import BallTree


EARTH_RADIUS_M = 6_371_000.0
_ROOT = Path(__file__).resolve().parents[3]
with (_ROOT / "backend/config/frozen_thresholds.json").open("r", encoding="utf-8") as _fh:
    _RESOLVER_CONFIG = json.load(_fh)["source_resolver"]
DEFAULT_EPS_M = float(_RESOLVER_CONFIG["eps_m"])
DEFAULT_MIN_SAMPLES = int(_RESOLVER_CONFIG["min_samples"])
BATCH_DELTA_REBUILD_INTERVAL = 256


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return EARTH_RADIUS_M * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class SourceResolver:
    def __init__(self, eps_m: float = DEFAULT_EPS_M, min_samples: int = DEFAULT_MIN_SAMPLES):
        if eps_m != DEFAULT_EPS_M or min_samples != DEFAULT_MIN_SAMPLES:
            raise ValueError("The frozen resolver is exactly 750 m with min_samples=3.")
        self.eps_m = eps_m
        self.min_samples = min_samples
        self.eps_rad = eps_m / EARTH_RADIUS_M
        # One entry per member detection; site IDs intentionally repeat.
        self.site_ids: List[str] = []
        self.site_coords: List[Tuple[float, float]] = []
        self.member_detection_ids: List[str] = []
        self._member_index: Dict[str, int] = {}
        self.site_tree: Optional[BallTree] = None
        self.candidates: Dict[str, Dict[str, Any]] = {}
        self._batch_active = False
        self._batch_pending_indices: set[int] = set()
        self._batch_dirty_indices: set[int] = set()
        self._batch_tree_indices: List[int] = []
        self._batch_tree: Optional[BallTree] = None
        self._candidate_member_ids: List[str] = []
        self._candidate_member_coords: List[Tuple[float, float]] = []
        self._candidate_tree: Optional[BallTree] = None
        self._candidate_tree_size = 0

    def load_members(self, member_records: List[Dict[str, Any]]) -> int:
        self.site_ids = []
        self.site_coords = []
        self.member_detection_ids = []
        self._member_index = {}
        for index, record in enumerate(member_records):
            detection_id = str(record.get("detection_id") or f"__loaded_member_{index}")
            if detection_id in self._member_index:
                continue
            self._member_index[detection_id] = len(self.site_ids)
            self.member_detection_ids.append(detection_id)
            self.site_ids.append(str(record["site_id"]))
            self.site_coords.append((float(record["latitude"]), float(record["longitude"])))
        self._rebuild_tree()
        return len(self.site_ids)

    def load_sites(self, site_records: List[Dict[str, Any]]) -> int:
        """Compatibility alias; records are interpreted as member points."""
        return self.load_members(site_records)

    def load_candidates(self, candidate_records: List[Dict[str, Any]]) -> int:
        self.candidates = {}
        self._candidate_member_ids = []
        self._candidate_member_coords = []
        for record in candidate_records:
            candidate_id = str(record["candidate_id"])
            detections = list(record.get("detections") or [])
            self.candidates[candidate_id] = {
                "candidate_id": candidate_id,
                "latitude": float(record["latitude"]),
                "longitude": float(record["longitude"]),
                "detection_count": len(detections) or int(record.get("detection_count", 0)),
                "detections": detections,
            }
            for detection in detections:
                self._append_candidate_member(candidate_id, detection)
        self._rebuild_candidate_tree()
        return len(self.candidates)

    def add_site_members(self, site_id: str, detections: List[Dict[str, Any]]) -> None:
        for detection in detections:
            self.upsert_site_member(site_id, detection, rebuild=False)
        if self._batch_active:
            self._rebuild_batch_tree()
        else:
            self._rebuild_tree()

    def begin_batch(self) -> None:
        """Defer rebuilding the full member tree while retaining incremental matches."""
        if self._batch_active:
            raise RuntimeError("A source-resolver batch is already active.")
        self._batch_active = True
        self._batch_pending_indices = set()
        self._batch_dirty_indices = set()
        self._batch_tree_indices = []
        self._batch_tree = None

    def end_batch(self) -> None:
        """Publish all batch members to one rebuilt primary spatial index."""
        if not self._batch_active:
            return
        self._batch_active = False
        self._rebuild_tree()
        self._batch_pending_indices = set()
        self._batch_dirty_indices = set()
        self._batch_tree_indices = []
        self._batch_tree = None

    def upsert_site_member(
        self, site_id: str, detection: Dict[str, Any], rebuild: bool = True
    ) -> None:
        detection_id = detection.get("detection_id")
        if not detection_id:
            return
        detection_id = str(detection_id)
        coordinate = (float(detection["latitude"]), float(detection["longitude"]))
        existing_index = self._member_index.get(detection_id)
        if existing_index is None:
            self._member_index[detection_id] = len(self.site_ids)
            self.member_detection_ids.append(detection_id)
            self.site_ids.append(str(site_id))
            self.site_coords.append(coordinate)
        else:
            self.site_ids[existing_index] = str(site_id)
            self.site_coords[existing_index] = coordinate
        member_index = self._member_index[detection_id]
        if self._batch_active:
            self._batch_pending_indices.add(member_index)
            self._batch_dirty_indices.add(member_index)
            if len(self._batch_dirty_indices) >= BATCH_DELTA_REBUILD_INTERVAL:
                self._rebuild_batch_tree()
        elif rebuild:
            self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        self.site_tree = (
            BallTree(np.radians(np.asarray(self.site_coords)), metric="haversine")
            if self.site_coords
            else None
        )

    def _rebuild_batch_tree(self) -> None:
        self._batch_tree_indices = sorted(self._batch_pending_indices)
        self._batch_tree = (
            BallTree(
                np.radians(np.asarray([self.site_coords[index] for index in self._batch_tree_indices])),
                metric="haversine",
            )
            if self._batch_tree_indices
            else None
        )
        self._batch_dirty_indices = set()

    def resolve_detection(
        self,
        latitude: float,
        longitude: float,
        detection_id: Optional[str] = None,
        detection_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        nearest_by_site: Dict[str, float] = {}

        def record_match(member_index: int, distance_m: float) -> None:
            site_id = self.site_ids[member_index]
            nearest_by_site[site_id] = min(nearest_by_site.get(site_id, math.inf), distance_m)

        if self.site_tree is not None:
            indices, distances = self.site_tree.query_radius(
                np.radians([[latitude, longitude]]),
                r=self.eps_rad,
                return_distance=True,
                sort_results=True,
            )
            for idx, distance in zip(indices[0], distances[0]):
                member_index = int(idx)
                if self._batch_active and member_index in self._batch_pending_indices:
                    continue
                record_match(member_index, float(distance) * EARTH_RADIUS_M)

        if self._batch_active and self._batch_tree is not None:
            indices, distances = self._batch_tree.query_radius(
                np.radians([[latitude, longitude]]),
                r=self.eps_rad,
                return_distance=True,
                sort_results=True,
            )
            for delta_index, distance in zip(indices[0], distances[0]):
                record_match(
                    self._batch_tree_indices[int(delta_index)],
                    float(distance) * EARTH_RADIUS_M,
                )

        if self._batch_active:
            for member_index in self._batch_dirty_indices:
                member_lat, member_lon = self.site_coords[member_index]
                distance_m = haversine_distance_m(
                    latitude, longitude, member_lat, member_lon
                )
                if distance_m <= self.eps_m:
                    record_match(member_index, distance_m)

        if nearest_by_site:
            candidates = sorted(nearest_by_site, key=lambda sid: (nearest_by_site[sid], sid))
            chosen = candidates[0]
            result = {
                "status": "MATCHED",
                "site_id": chosen,
                "distance_m": round(nearest_by_site[chosen], 2),
                "is_ambiguous": len(candidates) > 1,
                "candidate_site_ids": candidates,
                "detection_id": detection_id,
            }
            self.upsert_site_member(
                chosen,
                {
                    "detection_id": detection_id,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
            return result

        candidate_id, distance_m = self._nearest_candidate(latitude, longitude)
        detection = {
            "detection_id": detection_id,
            "latitude": latitude,
            "longitude": longitude,
            "payload": detection_payload,
        }
        if candidate_id is None:
            candidate_id = f"CAND_{uuid.uuid4().hex}"
            self.candidates[candidate_id] = {
                "candidate_id": candidate_id,
                "latitude": latitude,
                "longitude": longitude,
                "detection_count": 1,
                "detections": [detection],
            }
            self._append_candidate_member(candidate_id, detection)
            return {
                "status": "NEW_CANDIDATE",
                "candidate_id": candidate_id,
                "detection_count": 1,
                "detection_id": detection_id,
            }

        candidate = self.candidates[candidate_id]
        if detection_id not in {d.get("detection_id") for d in candidate["detections"]}:
            candidate["detections"].append(detection)
            self._append_candidate_member(candidate_id, detection)
        candidate["detection_count"] = len(candidate["detections"])
        candidate["latitude"] = float(np.mean([d["latitude"] for d in candidate["detections"]]))
        candidate["longitude"] = float(np.mean([d["longitude"] for d in candidate["detections"]]))

        if candidate["detection_count"] >= self.min_samples:
            site_id = f"INDIA_PROMOTED_{uuid.uuid4().hex}"
            members = list(candidate["detections"])
            self.add_site_members(site_id, members)
            del self.candidates[candidate_id]
            return {
                "status": "PROMOTED",
                "site_id": site_id,
                "candidate_id": candidate_id,
                "latitude": candidate["latitude"],
                "longitude": candidate["longitude"],
                "total_detections": candidate["detection_count"],
                "member_detections": members,
                "detection_id": detection_id,
            }

        return {
            "status": "CANDIDATE_ACCUMULATED",
            "candidate_id": candidate_id,
            "detection_count": candidate["detection_count"],
            "distance_m": round(distance_m, 2),
            "detection_id": detection_id,
        }

    def _nearest_candidate(self, latitude: float, longitude: float) -> Tuple[Optional[str], float]:
        best_id: Optional[str] = None
        best_distance = math.inf

        if self._candidate_tree is not None:
            indices, distances = self._candidate_tree.query_radius(
                np.radians([[latitude, longitude]]),
                r=self.eps_rad,
                return_distance=True,
                sort_results=True,
            )
            for index, distance in zip(indices[0], distances[0]):
                candidate_id = self._candidate_member_ids[int(index)]
                if candidate_id not in self.candidates:
                    continue
                distance_m = float(distance) * EARTH_RADIUS_M
                if distance_m < best_distance:
                    best_id = candidate_id
                    best_distance = distance_m

        for index in range(self._candidate_tree_size, len(self._candidate_member_ids)):
            candidate_id = self._candidate_member_ids[index]
            if candidate_id not in self.candidates:
                continue
            member_lat, member_lon = self._candidate_member_coords[index]
            distance_m = haversine_distance_m(
                latitude, longitude, member_lat, member_lon
            )
            if distance_m <= self.eps_m and distance_m < best_distance:
                best_id = candidate_id
                best_distance = distance_m
        return best_id, best_distance

    def _append_candidate_member(self, candidate_id: str, detection: Dict[str, Any]) -> None:
        self._candidate_member_ids.append(candidate_id)
        self._candidate_member_coords.append(
            (float(detection["latitude"]), float(detection["longitude"]))
        )
        if len(self._candidate_member_ids) - self._candidate_tree_size >= BATCH_DELTA_REBUILD_INTERVAL:
            self._rebuild_candidate_tree()

    def _rebuild_candidate_tree(self) -> None:
        self._candidate_tree = (
            BallTree(np.radians(np.asarray(self._candidate_member_coords)), metric="haversine")
            if self._candidate_member_coords
            else None
        )
        self._candidate_tree_size = len(self._candidate_member_ids)
