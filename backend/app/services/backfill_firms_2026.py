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
from pathlib import Path
import pandas as pd

from backend.app.services.firms_client import FirmsClient, DEFAULT_INDIA_BBOX, DEFAULT_PRIMARY_SOURCE
from backend.app.services.firms_ingestion import FirmsIngestionService
from backend.app.engines.source_resolver import SourceResolver
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.model_c import ModelCEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BOOTSTRAP_SITES = str(PROJECT_ROOT / "data" / "bootstrap" / "source_sites_ground_truth_FINAL.csv")
DEFAULT_DAILY_ACTIVITY = str(PROJECT_ROOT / "data" / "bootstrap" / "site_daily_activity.parquet")
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "data" / "backfill_2026")
DEFAULT_CACHE_DIR = str(PROJECT_ROOT / "data" / "cache" / "firms")


class BackfillOrchestrator:
    """
    Orchestrates sequential 2026 backfill from NASA FIRMS Area API.
    """

    def __init__(
        self,
        firms_client: Optional[FirmsClient] = None,
        source_resolver: Optional[SourceResolver] = None,
        ingestion_service: Optional[FirmsIngestionService] = None,
        bootstrap_sites_path: Optional[str] = None,
        daily_activity_path: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        self.client = firms_client or FirmsClient()
        self.resolver = source_resolver or SourceResolver(eps_m=750.0, min_samples=3)
        self.ingestion = ingestion_service or FirmsIngestionService(self.resolver)
        
        self.bootstrap_sites_path = bootstrap_sites_path or DEFAULT_BOOTSTRAP_SITES
        self.daily_activity_path = daily_activity_path or DEFAULT_DAILY_ACTIVITY
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR

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
                res = model_b_engine.predict_from_stats(stats)
                states.append({
                    "site_id": site_id,
                    "model_b_state": res["state"],
                    "confidence": res["confidence"],
                    "reason": res["reason"],
                    "days_since_last": stats.get("days_since_last"),
                    "active_days_30": stats.get("active_days_30", 0),
                    "active_days_90": stats.get("active_days_90", 0),
                    "active_days_180": stats.get("active_days_180", 0),
                    "active_days_365": stats.get("active_days_365", 0),
                    "as_of_date": as_of_date
                })
            except Exception:
                continue

        return pd.DataFrame(states)

    def update_database(
        self,
        promoted_sites: List[Dict[str, Any]],
        updated_daily_df: pd.DataFrame,
        states_df: pd.DataFrame,
        resolved_detections: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Updates PostgreSQL database tables with backfilled records:
        1. Promoted source_sites (and baseline Model A/B/C)
        2. site_daily_activity (2026 rows)
        3. site_model_b (recomputed 2026 states)
        4. firms_detections (normalized 2026 detections)
        """
        from backend.app.db.session import DEFAULT_DATABASE_URL
        import json
        from datetime import datetime, timezone
        import psycopg

        logger.info("Updating PostgreSQL database with backfill results...")
        conn_url = DEFAULT_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(conn_url, autocommit=False)
        now_iso = datetime.now(timezone.utc).isoformat()
        
        counts = {"sites_promoted": 0, "daily_activity_inserted": 0, "model_b_updated": 0, "detections_inserted": 0}

        try:
            with conn.cursor() as cur:
                # 1. Promoted sites
                if promoted_sites:
                    cur.execute("SELECT site_id FROM source_sites WHERE site_id LIKE 'INDIA_PROMOTED_%'")
                    existing_promoted = set(r[0] for r in cur.fetchall())
                    new_to_insert = [p for p in promoted_sites if p["site_id"] not in existing_promoted]
                    
                    if new_to_insert:
                        with cur.copy("COPY source_sites (site_id, latitude, longitude, status, created_at) FROM STDIN") as copy:
                            for p in new_to_insert:
                                copy.write_row((p["site_id"], float(p["latitude"]), float(p["longitude"]), "ACTIVE", now_iso))
                        
                        # Baseline Model A for promoted
                        with cur.copy("COPY site_model_a (site_id, core_probability, class_name, decision, prithvi_status, model_version, computed_at) FROM STDIN") as copy:
                            for p in new_to_insert:
                                copy.write_row((p["site_id"], 0.50, "UNKNOWN", "UNKNOWN", "NOT_TRIGGERED", "2026-09-04-r1", now_iso))
                                
                        # Baseline Model C for promoted
                        with cur.copy("COPY site_model_c (site_id, operational_status, model_version, computed_at) FROM STDIN") as copy:
                            for p in new_to_insert:
                                copy.write_row((p["site_id"], "INSUFFICIENT_HISTORY", "2026-09-04-r1", now_iso))
                                
                        counts["sites_promoted"] = len(new_to_insert)
                        logger.info(f"Inserted {len(new_to_insert)} newly promoted sites into source_sites.")

                # 2. site_daily_activity (2026 only)
                df_2026 = updated_daily_df[pd.to_datetime(updated_daily_df["acq_date"]) >= "2026-01-01"].copy()
                if not df_2026.empty:
                    cur.execute("""
                        CREATE TEMP TABLE tmp_daily_act (
                            site_id VARCHAR(64),
                            acq_date DATE,
                            detections INT,
                            mean_frp FLOAT,
                            max_frp FLOAT,
                            updated_at TIMESTAMP
                        ) ON COMMIT DROP;
                    """)
                    dates_str = pd.to_datetime(df_2026["acq_date"]).dt.strftime("%Y-%m-%d").tolist()
                    with cur.copy("COPY tmp_daily_act FROM STDIN") as copy:
                        for idx in range(len(df_2026)):
                            copy.write_row((
                                df_2026["site_id"].iat[idx],
                                dates_str[idx],
                                int(df_2026["detections"].iat[idx]),
                                float(df_2026["mean_frp"].iat[idx]),
                                float(df_2026["max_frp"].iat[idx]),
                                now_iso
                            ))
                    cur.execute("""
                        INSERT INTO site_daily_activity (site_id, acq_date, detections, mean_frp, max_frp, updated_at)
                        SELECT t.site_id, t.acq_date, t.detections, t.mean_frp, t.max_frp, t.updated_at
                        FROM tmp_daily_act t
                        JOIN source_sites s ON t.site_id = s.site_id
                        ON CONFLICT (site_id, acq_date) DO UPDATE
                        SET detections = EXCLUDED.detections,
                            mean_frp = EXCLUDED.mean_frp,
                            max_frp = EXCLUDED.max_frp,
                            updated_at = EXCLUDED.updated_at;
                    """)
                    counts["daily_activity_inserted"] = len(df_2026)
                    logger.info(f"Upserted {len(df_2026)} 2026 daily activity records into site_daily_activity.")

                # 3. site_model_b (recomputed 2026 states)
                if states_df is not None and not states_df.empty:
                    cur.execute("""
                        CREATE TEMP TABLE tmp_model_b (
                            site_id VARCHAR(64),
                            state VARCHAR(32),
                            confidence VARCHAR(16),
                            reason TEXT,
                            days_since_last INT,
                            active_days_windows JSONB,
                            computed_at TIMESTAMP
                        ) ON COMMIT DROP;
                    """)
                    with cur.copy("COPY tmp_model_b FROM STDIN") as copy:
                        for idx in range(len(states_df)):
                            sid = states_df["site_id"].iat[idx]
                            st = states_df["model_b_state"].iat[idx]
                            conf = states_df["confidence"].iat[idx]
                            reas = states_df["reason"].iat[idx]
                            dsl = int(states_df["days_since_last"].iat[idx]) if pd.notna(states_df.get("days_since_last", pd.Series([None])).iat[idx]) else None
                            wins = {
                                "30d": int(states_df.get("active_days_30", pd.Series([0])).iat[idx]) if pd.notna(states_df.get("active_days_30", pd.Series([0])).iat[idx]) else 0,
                                "90d": int(states_df.get("active_days_90", pd.Series([0])).iat[idx]) if pd.notna(states_df.get("active_days_90", pd.Series([0])).iat[idx]) else 0,
                                "180d": int(states_df.get("active_days_180", pd.Series([0])).iat[idx]) if pd.notna(states_df.get("active_days_180", pd.Series([0])).iat[idx]) else 0,
                                "365d": int(states_df.get("active_days_365", pd.Series([0])).iat[idx]) if pd.notna(states_df.get("active_days_365", pd.Series([0])).iat[idx]) else 0,
                            }
                            copy.write_row((sid, st, conf, reas, dsl, json.dumps(wins), now_iso))
                    
                    cur.execute("""
                        UPDATE site_model_b s
                        SET state = t.state,
                            confidence = t.confidence,
                            reason = t.reason,
                            days_since_last = t.days_since_last,
                            active_days_windows = t.active_days_windows,
                            computed_at = t.computed_at
                        FROM tmp_model_b t
                        WHERE s.site_id = t.site_id;
                    """)
                    cur.execute("""
                        INSERT INTO site_model_b (site_id, state, confidence, reason, days_since_last, active_days_windows, model_version, computed_at)
                        SELECT t.site_id, t.state, t.confidence, t.reason, t.days_since_last, t.active_days_windows, '2026-09-04-r1', t.computed_at
                        FROM tmp_model_b t
                        JOIN source_sites ss ON t.site_id = ss.site_id
                        WHERE t.site_id NOT IN (SELECT site_id FROM site_model_b);
                    """)
                    counts["model_b_updated"] = len(states_df)
                    logger.info(f"Updated {len(states_df)} Model B states in site_model_b.")

                # 4. firms_detections
                if resolved_detections:
                    cur.execute("""
                        CREATE TEMP TABLE tmp_firms_dets (
                            detection_id VARCHAR(64),
                            source_sensor VARCHAR(64),
                            satellite VARCHAR(16),
                            instrument VARCHAR(32),
                            latitude FLOAT,
                            longitude FLOAT,
                            acq_date DATE,
                            acq_time VARCHAR(8),
                            frp FLOAT,
                            bright_ti4 FLOAT,
                            bright_ti5 FLOAT,
                            scan FLOAT,
                            track FLOAT,
                            confidence VARCHAR(32),
                            daynight VARCHAR(4),
                            version VARCHAR(32),
                            source_site_id VARCHAR(64),
                            raw_payload JSONB,
                            ingested_at TIMESTAMP
                        ) ON COMMIT DROP;
                    """)
                    with cur.copy("COPY tmp_firms_dets FROM STDIN") as copy:
                        for d in resolved_detections:
                            acq_d = str(d["acq_date"])[:10]
                            raw_m = d.get("raw_payload") or {}
                            if not isinstance(raw_m, dict):
                                raw_m = {"raw": str(raw_m)}
                            raw_m["resolution_status"] = d.get("resolution_status", "UNKNOWN")
                            raw_m["distance_to_site_m"] = d.get("distance_m")
                            raw_m["is_ambiguous"] = d.get("is_ambiguous", False)

                            copy.write_row((
                                d["detection_id"],
                                d.get("source_sensor", "VIIRS_NOAA20_NRT"),
                                str(d.get("satellite", "20")),
                                d.get("instrument", "VIIRS"),
                                float(d["latitude"]),
                                float(d["longitude"]),
                                acq_d,
                                str(d.get("acq_time", "0000")),
                                float(d.get("frp", 0.0) or 0.0),
                                float(d["bright_ti4"]) if d.get("bright_ti4") is not None else None,
                                float(d["bright_ti5"]) if d.get("bright_ti5") is not None else None,
                                float(d["scan"]) if d.get("scan") is not None else None,
                                float(d["track"]) if d.get("track") is not None else None,
                                str(d.get("confidence")) if d.get("confidence") is not None else None,
                                str(d.get("daynight") or "D"),
                                str(d.get("version")) if d.get("version") is not None else None,
                                d.get("site_id"),
                                json.dumps(raw_m),
                                now_iso
                            ))
                    cur.execute("""
                        INSERT INTO firms_detections (
                            detection_id, source_sensor, satellite, instrument, latitude, longitude,
                            acq_date, acq_time, frp, bright_ti4, bright_ti5, scan, track,
                            confidence, daynight, version, source_site_id, raw_payload, ingested_at
                        )
                        SELECT
                            t.detection_id, t.source_sensor, t.satellite, t.instrument, t.latitude, t.longitude,
                            t.acq_date, t.acq_time, t.frp, t.bright_ti4, t.bright_ti5, t.scan, t.track,
                            t.confidence, t.daynight, t.version, t.source_site_id, t.raw_payload, t.ingested_at
                        FROM tmp_firms_dets t
                        LEFT JOIN source_sites s ON t.source_site_id = s.site_id
                        ON CONFLICT (detection_id) DO NOTHING;
                    """)
                    cur.execute("SELECT count(*) FROM tmp_firms_dets")
                    counts["detections_inserted"] = cur.fetchone()[0]
                    logger.info("Inserted raw FIRMS detections into firms_detections.")

            conn.commit()
            logger.info("Database transaction committed successfully.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update database: {e}", exc_info=True)
            raise
        finally:
            conn.close()

        return counts

    def run_backfill(
        self,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        source: str = DEFAULT_PRIMARY_SOURCE,
        bbox: str = DEFAULT_INDIA_BBOX,
        dry_run: bool = False,
        update_db: bool = False
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
        promoted_sites = []
        if total_promoted > 0:
            promoted_sites = [
                {"site_id": s_id, "latitude": lat, "longitude": lon}
                for s_id, (lat, lon) in zip(self.resolver.site_ids, self.resolver.site_coords)
                if s_id.startswith("INDIA_PROMOTED_")
            ]

        states_df = pd.DataFrame()
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
            if promoted_sites:
                promoted_df = pd.DataFrame(promoted_sites)
                promoted_out = os.path.join(self.output_dir, "promoted_sites_2026.csv")
                promoted_df.to_csv(promoted_out, index=False)
                output_paths["promoted_sites"] = promoted_out
                logger.info(f"Saved {len(promoted_df)} promoted sites to {promoted_out}")

            # Update PostgreSQL database if requested
            if update_db:
                db_counts = self.update_database(
                    promoted_sites=promoted_sites,
                    updated_daily_df=updated_daily_df,
                    states_df=states_df,
                    resolved_detections=all_resolved_detections
                )
                output_paths["database_update"] = db_counts

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
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="Directory to cache FIRMS responses")
    parser.add_argument("--update-db", action="store_true", help="Update PostgreSQL database tables with backfilled records")
    args = parser.parse_args()

    client = FirmsClient(map_key=args.map_key, offline_mode=args.offline, cache_dir=args.cache_dir)
    orchestrator = BackfillOrchestrator(firms_client=client)
    res = orchestrator.run_backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        update_db=args.update_db
    )
    print("\n=== Backfill Summary ===")
    for k, v in res.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
