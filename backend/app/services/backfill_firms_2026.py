"""
2026 FIRMS Backfill Orchestrator
Backfills NOAA-20 NRT detections from 2026-01-01 to the target deployment date in <=5-day windows.
Incrementally updates source sites, daily activity, and recalculates Model B & Model C states.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path when invoked directly as a script
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from backend.app.services.firms_client import FirmsClient, DEFAULT_INDIA_BBOX, DEFAULT_PRIMARY_SOURCE
from backend.app.services.firms_ingestion import FirmsIngestionService
from backend.app.engines.source_resolver import SourceResolver
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.model_c import ModelCEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class BackfillOrchestrator:
    """
    Orchestrates sequential 2026 backfill from NASA FIRMS Area API.
    """

    def __init__(
        self,
        firms_client: Optional[FirmsClient] = None,
        source_resolver: Optional[SourceResolver] = None,
        ingestion_service: Optional[FirmsIngestionService] = None,
        bootstrap_sites_path: str = "data/bootstrap/source_sites_ground_truth_FINAL.csv",
        daily_activity_path: str = "data/bootstrap/site_daily_activity.parquet",
        output_dir: str = "data/backfill_2026"
    ):
        self.client = firms_client or FirmsClient()
        self.resolver = source_resolver or SourceResolver(eps_m=750.0, min_samples=3)
        self.ingestion = ingestion_service or FirmsIngestionService(self.resolver)
        
        self.bootstrap_sites_path = bootstrap_sites_path
        self.daily_activity_path = daily_activity_path
        self.output_dir = output_dir

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def generate_5day_windows(start_date_str: str, end_date_str: str) -> List[Tuple[str, int]]:
        """
        Partitions date span into contiguous <= 5-day windows.
        Returns list of (window_start_date_str, day_count).
        """
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        if start > end:
            raise ValueError(f"start_date {start_date_str} is after end_date {end_date_str}")

        windows = []
        current = start
        while current <= end:
            days_left = (end - current).days + 1
            chunk_days = min(5, days_left)
            windows.append((current.strftime("%Y-%m-%d"), chunk_days))
            current += timedelta(days=chunk_days)

        return windows

    def load_bootstrap_data(self) -> Tuple[int, pd.DataFrame]:
        """
        Loads 79,365 frozen sites into the spatial resolver and loads existing daily activity.
        """
        logger.info(f"Loading bootstrap sites from {self.bootstrap_sites_path}...")
        if os.path.exists(self.bootstrap_sites_path):
            sites_df = pd.read_csv(
                self.bootstrap_sites_path,
                usecols=["site_id", "latitude", "longitude"],
                low_memory=False
            )
            sites_records = sites_df[["site_id", "latitude", "longitude"]].to_dict("records")
            self.resolver.load_sites(sites_records)
            sites_loaded = len(sites_records)
            logger.info(f"Loaded {sites_loaded} existing sites into SourceResolver.")
        else:
            logger.warning(f"Bootstrap sites file not found at {self.bootstrap_sites_path}.")
            sites_loaded = 0

        logger.info(f"Loading existing daily activity from {self.daily_activity_path}...")
        if os.path.exists(self.daily_activity_path):
            daily_df = pd.read_parquet(self.daily_activity_path)
            daily_df["acq_date"] = pd.to_datetime(daily_df["acq_date"])
            logger.info(f"Loaded {len(daily_df)} historical daily activity rows.")
        else:
            daily_df = pd.DataFrame(columns=["site_id", "acq_date", "detections", "mean_frp", "max_frp"])
            logger.warning(f"Daily activity file not found at {self.daily_activity_path}. Starting fresh.")

        return sites_loaded, daily_df

    def recompute_model_b_states(self, daily_df: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
        """
        Recomputes Model B states across all sites in daily_df as of the target date.
        """
        logger.info(f"Recomputing Model B states as of {as_of_date}...")
        model_b_engine = ModelBEngine()
        
        grouped = daily_df.groupby("site_id")["acq_date"].apply(list)
        states = []
        for site_id, active_dates in grouped.items():
            try:
                stats = model_b_engine.compute_timeline_stats(active_dates, as_of_date=as_of_date)
                res = model_b_engine.predict(stats)
                states.append({
                    "site_id": site_id,
                    "model_b_state": res["state"],
                    "confidence": res["confidence"],
                    "reason": res["reason"],
                    "as_of_date": as_of_date
                })
            except Exception:
                continue

        return pd.DataFrame(states)

    def run_backfill(
        self,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        source: str = DEFAULT_PRIMARY_SOURCE,
        bbox: str = DEFAULT_INDIA_BBOX,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the backfill pipeline from start_date to end_date.
        """
        target_end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        windows = self.generate_5day_windows(start_date, target_end_date)
        logger.info(f"Generated {len(windows)} backfill windows from {start_date} to {target_end_date}.")

        sites_loaded, existing_daily_df = self.load_bootstrap_data()

        total_fetched = 0
        total_unique = 0
        total_matched = 0
        total_promoted = 0
        all_resolved_detections: List[Dict[str, Any]] = []

        for idx, (win_date, day_span) in enumerate(windows, 1):
            logger.info(f"[{idx}/{len(windows)}] Fetching {source} from {win_date} ({day_span} days)...")
            try:
                raw_rows = self.client.fetch_area_detections(
                    source=source,
                    bbox=bbox,
                    day_range=day_span,
                    date=win_date
                )
            except Exception as e:
                logger.error(f"Error fetching window {win_date}: {e}")
                raw_rows = []

            total_fetched += len(raw_rows)

            if raw_rows:
                batch_result = self.ingestion.ingest_batch(
                    raw_records=raw_rows,
                    source_resolver=self.resolver,
                    source_sensor=source
                )
                total_unique += batch_result["unique_count"]
                total_matched += batch_result["matched_count"]
                total_promoted += batch_result["promoted_count"]
                all_resolved_detections.extend(batch_result["resolved_detections"])
                logger.info(
                    f"Processed {len(raw_rows)} rows: {batch_result['matched_count']} matched, "
                    f"{batch_result['promoted_count']} promoted to new sites."
                )

        # Aggregate daily activity
        logger.info("Aggregating daily activity with historical baseline...")
        updated_daily_df = self.ingestion.aggregate_daily_activity(
            resolved_detections=all_resolved_detections,
            existing_daily_df=existing_daily_df
        )

        output_paths = {}
        if not dry_run:
            daily_out = os.path.join(self.output_dir, "site_daily_activity_2026.parquet")
            updated_daily_df.to_parquet(daily_out, index=False)
            output_paths["daily_activity"] = daily_out
            logger.info(f"Saved updated daily activity ({len(updated_daily_df)} rows) to {daily_out}")

            # Recompute and save Model B states through the target date
            states_df = self.recompute_model_b_states(updated_daily_df, as_of_date=target_end_date)
            states_out = os.path.join(self.output_dir, "MODEL_B_SOURCE_STATES_2026.csv")
            states_df.to_csv(states_out, index=False)
            output_paths["model_b_states"] = states_out
            logger.info(f"Saved recomputed Model B states ({len(states_df)} sites) to {states_out}")

            # Save newly promoted sites if any
            if total_promoted > 0:
                promoted_sites = [
                    {"site_id": s_id, "latitude": lat, "longitude": lon}
                    for s_id, (lat, lon) in zip(self.resolver.site_ids, self.resolver.site_coords)
                    if s_id.startswith("INDIA_PROMOTED_")
                ]
                if promoted_sites:
                    promoted_df = pd.DataFrame(promoted_sites)
                    promoted_out = os.path.join(self.output_dir, "promoted_sites_2026.csv")
                    promoted_df.to_csv(promoted_out, index=False)
                    output_paths["promoted_sites"] = promoted_out
                    logger.info(f"Saved {len(promoted_df)} promoted sites to {promoted_out}")

        return {
            "start_date": start_date,
            "end_date": target_end_date,
            "total_windows": len(windows),
            "total_fetched": total_fetched,
            "total_unique": total_unique,
            "total_matched": total_matched,
            "total_promoted": total_promoted,
            "updated_daily_rows": len(updated_daily_df),
            "output_paths": output_paths,
            "dry_run": dry_run
        }


def main():
    parser = argparse.ArgumentParser(description="NASA FIRMS 2026 Backfill CLI")
    parser.add_argument("--start-date", default="2026-01-01", help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--map-key", default=None, help="NASA FIRMS MAP_KEY (defaults to FIRMS_MAP_KEY in .env)")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without writing files")
    parser.add_argument("--offline", action="store_true", help="Run in offline mode")
    parser.add_argument("--cache-dir", default="data/cache/firms", help="Directory to cache FIRMS responses")
    args = parser.parse_args()

    client = FirmsClient(map_key=args.map_key, offline_mode=args.offline, cache_dir=args.cache_dir)
    orchestrator = BackfillOrchestrator(firms_client=client)
    res = orchestrator.run_backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run
    )
    print("\n=== Backfill Summary ===")
    for k, v in res.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
