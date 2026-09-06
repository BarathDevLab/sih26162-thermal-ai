"""
CLI Entry point for 2026 FIRMS Backfill
Usage:
  python backend/scripts/backfill_firms_2026.py --start-date 2026-01-01
"""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.services.backfill_firms_2026 import main

if __name__ == "__main__":
    main()
