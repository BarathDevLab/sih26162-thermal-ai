import math
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd

class ModelBEngine:
    """
    Deterministic Temporal State Engine for SIH26162.
    Evaluates 5 mutually exclusive states in frozen precedence:
    REACTIVATED -> NEW -> PERSISTENT -> DORMANT -> INTERMITTENT
    """

    def __init__(self):
        self.precedence = ["REACTIVATED", "NEW", "PERSISTENT", "DORMANT", "INTERMITTENT"]

    def compute_timeline_stats(
        self,
        active_dates: List[Union[date, datetime, str]],
        as_of_date: Union[date, datetime, str]
    ) -> Dict[str, Any]:
        if not active_dates:
            raise ValueError("active_dates list cannot be empty.")

        # Convert as_of_date
        if isinstance(as_of_date, str):
            ref_date = datetime.strptime(as_of_date[:10], "%Y-%m-%d").date()
        elif isinstance(as_of_date, datetime):
            ref_date = as_of_date.date()
        else:
            ref_date = as_of_date

        # Convert and filter active dates <= as_of_date (no future leakage!)
        parsed_dates = []
        for d in active_dates:
            if isinstance(d, str):
                dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
            elif isinstance(d, datetime):
                dt = d.date()
            else:
                dt = d
            if dt <= ref_date:
                parsed_dates.append(dt)

        if not parsed_dates:
            raise ValueError(f"No active dates on or before as_of_date ({ref_date}).")

        unique_dates = sorted(list(set(parsed_dates)))
        first_seen = unique_dates[0]
        last_seen = unique_dates[-1]

        days_since_first = (ref_date - first_seen).days
        days_since_last = (ref_date - last_seen).days
        lifetime_days = (last_seen - first_seen).days + 1
        active_days_total = len(unique_dates)

        # Trailing windows from ref_date
        active_days_30 = sum(1 for d in unique_dates if (ref_date - d).days < 30)
        active_days_90 = sum(1 for d in unique_dates if (ref_date - d).days < 90)
        active_days_180 = sum(1 for d in unique_dates if (ref_date - d).days < 180)
        active_days_365 = sum(1 for d in unique_dates if (ref_date - d).days < 365)

        # Distinct months in trailing 180 days
        months_180 = set((d.year, d.month) for d in unique_dates if (ref_date - d).days < 180)
        active_months_180 = len(months_180)

        # Gaps analysis
        last_long_gap_days = None
        reactivation_age_days = None

        if len(unique_dates) > 1:
            for i in range(len(unique_dates) - 1):
                gap = (unique_dates[i+1] - unique_dates[i]).days
                if gap >= 90:
                    last_long_gap_days = float(gap)
                    reactivation_start = unique_dates[i+1]
                    reactivation_age_days = float((ref_date - reactivation_start).days)

        return {
            "ref_date": ref_date,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "days_since_first": days_since_first,
            "days_since_last": days_since_last,
            "lifetime_days": lifetime_days,
            "active_days_total": active_days_total,
            "active_days_30": active_days_30,
            "active_days_90": active_days_90,
            "active_days_180": active_days_180,
            "active_days_365": active_days_365,
            "active_months_180": active_months_180,
            "last_long_gap_days": last_long_gap_days,
            "reactivation_age_days": reactivation_age_days
        }

    def predict_from_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        dsl = stats["days_since_last"]
        dsf = stats["days_since_first"]
        life = stats["lifetime_days"]
        am180 = stats["active_months_180"]
        ad180 = stats["active_days_180"]
        ad30 = stats["active_days_30"]
        llg = stats.get("last_long_gap_days")
        rag = stats.get("reactivation_age_days")

        # 1. REACTIVATED
        if (dsl <= 30 and dsf > 30 and llg is not None and not pd.isna(llg) and llg >= 90 and
                rag is not None and not pd.isna(rag) and rag <= 30):
            state = "REACTIVATED"
            if ad30 == 1:
                conf = "LOW"
            elif ad30 >= 3 and llg >= 180:
                conf = "HIGH"
            else:
                conf = "MEDIUM"
            reason = "Returned within 30d after >=90d inactive gap"
            return {"state": state, "confidence": conf, "reason": reason, "stats": stats}

        # 2. NEW
        if dsl <= 30 and dsf <= 30:
            state = "NEW"
            if ad30 == 1:
                conf = "LOW"
            elif ad30 >= 3:
                conf = "HIGH"
            else:
                conf = "MEDIUM"
            reason = "First observed within 30d and currently active"
            return {"state": state, "confidence": conf, "reason": reason, "stats": stats}

        # 3. PERSISTENT
        if dsl <= 30 and life >= 90 and am180 >= 3 and ad180 >= 6:
            state = "PERSISTENT"
            if am180 >= 4 and ad180 >= 12:
                conf = "HIGH"
            else:
                conf = "MEDIUM"
            reason = "Currently active with >=90d history and repeated recent activity"
            return {"state": state, "confidence": conf, "reason": reason, "stats": stats}

        # 4. DORMANT
        if dsl > 90:
            state = "DORMANT"
            if dsl >= 180:
                conf = "HIGH"
            else:
                conf = "MEDIUM"
            reason = "No detection for >90d"
            return {"state": state, "confidence": conf, "reason": reason, "stats": stats}

        # 5. INTERMITTENT
        return {
            "state": "INTERMITTENT",
            "confidence": "MEDIUM",
            "reason": "Irregular activity not meeting other state rules",
            "stats": stats
        }

    def predict(
        self,
        active_dates: List[Union[date, datetime, str]],
        as_of_date: Union[date, datetime, str]
    ) -> Dict[str, Any]:
        stats = self.compute_timeline_stats(active_dates, as_of_date)
        return self.predict_from_stats(stats)
