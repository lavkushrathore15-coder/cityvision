# CITYVISION AI

**City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics**  
*Problem Statement ID: SIH26127*

---

## 1. Project Overview

CITYVISION AI is an intelligent urban surveillance and traffic intelligence system designed to process multi-camera CCTV video streams. It performs automated vehicle detection, multi-object tracking, license plate detection with OCR (ANPR), visual appearance Re-Identification (Re-ID), spatio-temporal cross-camera vehicle association, trajectory reconstruction on GIS maps, and real-time incident alerting.

### Core Pipeline Architecture

```
CCTV / Recorded Video Streams (5-10 Nodes)
  ↓
Vehicle Detection (YOLOv8 / YOLO11)
  ↓
Multi-Object Tracking (ByteTrack)
  ↓
License Plate Detection + OCR (ANPR) & Vehicle Re-Identification (Appearance Embeddings)
  ↓
Spatio-Temporal Cross-Camera Matcher (Road Topology Constraints)
  ↓
Global Vehicle ID Association
  ↓
Trajectory Reconstruction & GIS Coordinate Mapping
  ↓
Alerts (Watchlist & Incident Engine) + Urban Traffic Analytics
```

---

## 2. Directory Structure

```
cityvision.ai/
├── ai/                     # AI/CV Contracts, Interfaces & Model Implementations
│   ├── detectors/          # Vehicle detection abstract base classes & YOLO drivers
│   ├── trackers/           # Multi-object tracking (ByteTrack / Kalman) contracts
│   ├── anpr/               # License plate localization & OCR character recognition
│   ├── reid/               # Visual appearance feature extractor (OSNet / Re-ID)
│   └── matching/           # Spatio-temporal cross-camera trajectory associate
├── backend/                # FastAPI Telemetry & Trajectory Backend
│   └── app/
│       ├── api/            # REST endpoints & WebSocket telemetry routes
│       ├── core/           # Configuration & environment variables
│       ├── schemas/        # Pydantic data models for cameras, tracks, trajectories
│       └── services/       # Video ingestion, matching, alerts, analytics services
├── config/                 # Camera topologies & system runtime parameters
│   └── cameras.yaml        # Geographic coordinates & stream sources of CCTV nodes
├── data/                   # Data directory (cameras, test videos, watchlists)
│   ├── cameras/            # Seed camera configurations
│   ├── sample_videos/      # Recorded/synthetic CCTV traffic clips
│   └── watchlist/          # Stolen vehicle & wanted registration database
├── docs/                   # Engineering Architecture & API Specifications
│   ├── ARCHITECTURE.md     # In-depth system design & pipeline mechanics
│   ├── DATA_PIPELINE.md    # Association logic & mathematical formulations
│   └── API_SPEC.md         # REST & WebSocket endpoint documentation
├── frontend/               # React + TypeScript + Vite GIS Operations Dashboard
│   ├── src/
│   │   ├── components/     # Command Center, CCTV Feeds, Search, Map, Alerts
│   │   ├── services/       # Backend API integration client
│   │   └── types/          # TypeScript interfaces for entities & telemetry
│   └── package.json
├── models/                 # Model artifacts & weights storage
│   └── weights/            # Serialized weights (.pt, .onnx)
├── scripts/                # Utility scripts & synthetic data generators
│   ├── download_sample_data.py  # Offline synthetic CCTV video generator
│   ├── run_backend.py           # Local development server runner
│   └── setup_env.ps1            # Windows PowerShell automated setup
├── tests/                  # Automated unit test suite
├── .env.example            # Environment configuration template
├── .gitignore              # Git ignore rules for AI weights & node_modules
├── docker-compose.yml      # Orchestration for Backend, Frontend, PostGIS & Redis
├── Dockerfile.backend      # Containerfile for Python AI runtime
├── Dockerfile.frontend     # Multi-stage Containerfile for React NGINX deployment
└── requirements.txt        # Python dependency manifest
```

---

## 3. Development Setup

### Prerequisites
- **Python**: 3.10 – 3.13
- **Node.js**: v18+ (tested on Node v24)
- **NPM**: v9+ (tested on NPM v11)

### 3.1 Environment Setup (Windows / Linux)

```powershell
# 1. Clone repository and navigate
cd cityvision.ai

# 2. Run automated setup script (PowerShell)
.\scripts\setup_env.ps1

# Or manually:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Generate synthetic multi-camera CCTV clips for offline testing
python scripts/download_sample_data.py

# 4. Run tests
pytest
```

### 3.2 Running the Application

**Unified Server (Frontend Dashboard + AI Backend on Single Port)**:
```powershell
.\.venv\Scripts\python.exe scripts/run_backend.py
```
* **Command Center Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000) (or [http://localhost:8000](http://localhost:8000))
* **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc API Spec**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

*(Optional) Independent Frontend Development Mode (Hot Module Replacement)*:
```powershell
cd frontend
npm run dev
# Dev server runs on: http://localhost:5173
```

---

## 4. Current Implementation Status (All Phases Completed)

* [x] **Phase 1 (Foundation & Architecture)**: Modular repository scaffolding, abstract AI interfaces (`BaseVehicleDetector`, `BaseTracker`, `BasePlateDetector`, `BasePlateOCR`, `BaseVehicleReID`, `BaseCrossCameraMatcher`), Pydantic schemas, Docker orchestration, and synthetic CCTV generator.
* [x] **Phase 2 (Vehicle Detection)**: YOLOv8 vehicle detection (`ai/detectors/yolo.py`, `backend/app/services/detection.py`), class filtering, bounding box normalization, and CPU inference benchmarking.
* [x] **Phase 3 (Multi-Object Tracking)**: ByteTrack single-camera tracking (`ai/trackers/byte_tracker.py`, `backend/app/services/tracking.py`) with Kalman filter motion model, two-stage Hungarian association, and tracklet lifecycle management.
* [x] **Phase 4 (ANPR & OCR Engine)**: Automatic Number Plate Recognition (`ai/anpr/`, `backend/app/services/anpr.py`), morphological candidate plate detection, bilateral filtering, Otsu thresholding, EasyOCR inference, plate number normalization, and tracklet multi-frame consensus voting.
* [x] **Phase 5 (Re-ID & Cross-Camera Association)**: Vehicle appearance feature extraction (`ai/reid/`, `backend/app/services/reid.py`) with 256/512-dim unit-hypersphere embeddings, cosine similarity metrics, and spatio-temporal road topology graph matcher (`ai/matching/`, `backend/app/services/cross_camera.py`) with physical transit-time feasibility and conflict vetoes.
* [x] **Phase 6 (Database & Trajectory Subsystem)**: PostGIS & SQLite database backend (`backend/app/db/`), chronological trajectory reconstruction (`backend/app/services/trajectory.py`), camera visit dwell times, velocity calculation, and alert engine (`backend/app/services/alert_engine.py`) with stolen vehicle watchlist matching and speed violation alerts.
* [x] **Phase 7 (Pipeline Orchestrator & Telemetry API)**: 14-stage unified execution orchestrator (`backend/app/services/pipeline_orchestrator.py`), dual-mode runtime (Real CCTV & Isolated Demo Simulation), 33 REST endpoints, and WebSocket telemetry broadcaster (`/ws/telemetry`).
* [x] **Phase 8 (GIS Command Center Dashboard)**: React 19 + TypeScript + Vite operations dashboard (`frontend/`), interactive Leaflet GIS map with trajectory path lines, multi-camera CCTV grid with video playback, global plate search & filter, vehicle dossier modal, real-time alert notifications, and traffic analytics charts.
* [x] **Automated Test Suite**: 146 unit & integration tests passing across all subsystems (`pytest`).
