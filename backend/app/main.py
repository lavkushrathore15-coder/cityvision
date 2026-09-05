"""
CITYVISION AI - Main Backend Application Entry Point
FastAPI Application with CORS middleware, structured error responses, and logging.
Problem Statement ID: SIH26127
"""
import logging
import datetime
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import BASE_DIR, settings
from backend.app.api.routes import router as api_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cityvision.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Formats HTTP exceptions into standard structured ErrorResponse."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "code": f"ERR_HTTP_{exc.status_code}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation errors into standard structured ErrorResponse."""
    errors = exc.errors()
    error_msg = "; ".join([f"{err.get('loc')}: {err.get('msg')}" for err in errors])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": error_msg,
            "code": "ERR_VALIDATION",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


# Register API routes
app.include_router(api_router)

# -----------------------------------------------------------------------------
# Frontend Static Asset & Single-Page Application (SPA) Serving
# -----------------------------------------------------------------------------
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend_assets")

# Serve sample surveillance demo videos directly for real-time video playback
SAMPLE_VIDEOS_DIR = BASE_DIR / "data" / "sample_videos"
FRONTEND_DEMO_DIR = BASE_DIR / "frontend" / "public" / "demo_videos"

demo_static_dir = None
if FRONTEND_DEMO_DIR.is_dir():
    demo_static_dir = FRONTEND_DEMO_DIR
elif SAMPLE_VIDEOS_DIR.is_dir():
    demo_static_dir = SAMPLE_VIDEOS_DIR

if demo_static_dir:
    app.mount("/demo_videos", StaticFiles(directory=str(demo_static_dir)), name="demo_videos")


@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    fav = FRONTEND_DIST / "favicon.svg"
    if fav.is_file():
        return FileResponse(fav)
    raise HTTPException(status_code=404, detail="Not Found")


@app.get("/icons.svg", include_in_schema=False)
async def serve_icons():
    icons = FRONTEND_DIST / "icons.svg"
    if icons.is_file():
        return FileResponse(icons)
    raise HTTPException(status_code=404, detail="Not Found")


@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    """Explicit endpoint to serve the React operations dashboard."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Frontend build not found. Run 'npm run build' in frontend.")


@app.get("/", tags=["System"])
def root_endpoint(request: Request):
    """
    Root endpoint:
    - Serves the compiled React Frontend Dashboard to web browsers.
    - Serves operational system status JSON to API clients / test suites.
    """
    accept_header = request.headers.get("accept", "")
    index_file = FRONTEND_DIST / "index.html"
    if "text/html" in accept_header and index_file.is_file():
        return FileResponse(index_file)
    return {
        "service": settings.PROJECT_NAME,
        "status": "operational",
        "documentation": "/docs",
        "dashboard": "/",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_fallback(full_path: str):
    """Fallback handler for HTML5 client-side routing in React SPA."""
    if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404, detail="Not Found")

    file_path = FRONTEND_DIST / full_path
    if file_path.is_file():
        return FileResponse(file_path)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Not Found")
