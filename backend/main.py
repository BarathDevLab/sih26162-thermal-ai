"""Compatibility entry point for running ``uvicorn main:app`` from backend/.

The canonical application lives in :mod:`backend.app.main`. Keeping this shim
prevents local development commands from accidentally starting a reduced API.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402,F401


__all__ = ["app"]
