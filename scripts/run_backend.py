"""
Unified Server Runner for CITYVISION AI
Runs both Frontend (React Dashboard) and Backend (FastAPI + AI Engine) on a single port.
"""
import os
import sys
import subprocess
from pathlib import Path

# Ensure root workspace is in sys.path
BASE_ROOT = Path(__file__).resolve().parent.parent
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))

import uvicorn
from backend.app.core.config import settings, BASE_DIR

if __name__ == "__main__":
    frontend_dist = BASE_DIR / "frontend" / "dist"
    if not (frontend_dist / "index.html").exists():
        print("[INFO] Frontend dist not found. Building React dashboard...")
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        try:
            subprocess.run([npm_cmd, "run", "build"], cwd=str(BASE_DIR / "frontend"), check=True)
            print("[INFO] Frontend build completed successfully.")
        except Exception as e:
            print(f"[WARN] Could not automatically build frontend: {e}")

    print("=======================================================")
    print(f"  {settings.PROJECT_NAME} - Unified Command Center")
    print(f"  Dashboard & API:    http://{settings.HOST}:{settings.PORT}")
    print(f"  Interactive Docs:   http://{settings.HOST}:{settings.PORT}/docs")
    print(f"  ReDoc Specification: http://{settings.HOST}:{settings.PORT}/redoc")
    print("=======================================================\n")

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
