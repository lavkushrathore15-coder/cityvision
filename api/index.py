"""
Vercel Serverless Function entrypoint for CITYVISION AI FastAPI Backend.
Exposes the FastAPI application instance `app`.
"""
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
BASE_ROOT = Path(__file__).resolve().parent.parent
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))

from backend.app.main import app  # noqa: F401
