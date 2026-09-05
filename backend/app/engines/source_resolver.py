import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6371000.0
DEFAULT_EPS_M = 750.0
DEFAULT_MIN_SAMPLES = 3

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c

class SourceResolver:
    def __init__(self, eps_m: float = DEFAULT_EPS_M, min_samples: int = DEFAULT_MIN_SAMPLES):
        self.eps_m = eps_m
        self.min_samples = min_samples
        self.eps_rad = eps_m / EARTH_RADIUS_M
        
        self.site_ids: List[str] = []
        self.site_coords: List[Tuple[float, float]] = []  # (lat, lon)
        self.site_tree: Optional[BallTree] = None
        
        self.candidates: Dict[str, Dict[str, Any]] = {}
        self.next_candidate_idx = 1
        self.next_promoted_idx = 1

    def load_sites(self, site_records: List[Dict[str, Any]]) -> int:
        self.site_ids = []
        self.site_coords = []
        coords_rad = []
        
        for record in site_records:
            self.site_ids.append(record['site_id'])
            lat, lon = float(record['latitude']), float(record['longitude'])
            self.site_coords.append((lat, lon))
            coords_rad.append([math.radians(lat), math.radians(lon)])
            
        if coords_rad:
            self.site_tree = BallTree(np.array(coords_rad), metric='haversine')
        else:
            self.site_tree = None
        return len(self.site_ids)

    def _rebuild_tree(self):
        if self.site_coords:
            coords_rad = np.radians(np.array(self.site_coords))
            self.site_tree = BallTree(coords_rad, metric='haversine')
        else:
            self.site_tree = None

    def resolve_detection(
        self,
        latitude: float,
        longitude: float,
        detection_id: Optional[str] = None,
        detection_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        det_rad = np.radians([[latitude, longitude]])
        
        # 1. Search existing frozen/promoted source sites
        if self.site_tree is not None and len(self.site_ids) > 0:
            indices, dists = self.site_tree.query_radius(
                det_rad, r=self.eps_rad, return_distance=True, sort_results=True
            )
            matched_indices = indices[0]
            matched_dists = dists[0]
            
            if len(matched_indices) > 0:
                best_idx = matched_indices[0]
                best_site_id = self.site_ids[best_idx]
                best_dist_m = float(matched_dists[0]) * EARTH_RADIUS_M
                is_ambiguous = len(matched_indices) > 1
                
                return {
                    "status": "MATCHED",
                    "site_id": best_site_id,
                    "distance_m": round(best_dist_m, 2),
                    "is_ambiguous": is_ambiguous,
                    "candidate_site_ids": [self.site_ids[i] for i in matched_indices],
                    "detection_id": detection_id
                }

        # 2. Check candidate pool if no existing site matched
        best_cand_id = None
        best_cand_dist = float('inf')
        
        for cand_id, cand in self.candidates.items():
            dist = haversine_distance_m(latitude, longitude, cand['latitude'], cand['longitude'])
            if dist <= self.eps_m and dist < best_cand_dist:
                best_cand_dist = dist
                best_cand_id = cand_id

        if best_cand_id is not None:
            cand = self.candidates[best_cand_id]
            cand['detections'].append({
                'detection_id': detection_id,
                'latitude': latitude,
                'longitude': longitude,
                'payload': detection_payload
            })
            cand['detection_count'] += 1
            # Update centroid as running average
            cand['latitude'] = sum(d['latitude'] for d in cand['detections']) / cand['detection_count']
            cand['longitude'] = sum(d['longitude'] for d in cand['detections']) / cand['detection_count']
            
            # Check promotion criteria
            if cand['detection_count'] >= self.min_samples:
                promoted_site_id = f"INDIA_PROMOTED_{self.next_promoted_idx:06d}"
                self.next_promoted_idx += 1
                
                # Add to permanent active sites
                self.site_ids.append(promoted_site_id)
                self.site_coords.append((cand['latitude'], cand['longitude']))
                self._rebuild_tree()
                
                promoted_info = {
                    "status": "PROMOTED",
                    "site_id": promoted_site_id,
                    "candidate_id": best_cand_id,
                    "latitude": cand['latitude'],
                    "longitude": cand['longitude'],
                    "total_detections": cand['detection_count'],
                    "detection_id": detection_id
                }
                del self.candidates[best_cand_id]
                return promoted_info
            
            return {
                "status": "CANDIDATE_ACCUMULATED",
                "candidate_id": best_cand_id,
                "detection_count": cand['detection_count'],
                "distance_m": round(best_cand_dist, 2),
                "detection_id": detection_id
            }

        # 3. Create new candidate
        cand_id = f"CAND_{self.next_candidate_idx:06d}"
        self.next_candidate_idx += 1
        self.candidates[cand_id] = {
            "candidate_id": cand_id,
            "latitude": latitude,
            "longitude": longitude,
            "detection_count": 1,
            "detections": [{
                'detection_id': detection_id,
                'latitude': latitude,
                'longitude': longitude,
                'payload': detection_payload
            }]
        }
        
        return {
            "status": "NEW_CANDIDATE",
            "candidate_id": cand_id,
            "detection_count": 1,
            "detection_id": detection_id
        }
