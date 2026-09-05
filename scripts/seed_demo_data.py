"""
CITYVISION AI - High-Density Demo Dataset Generator
Populates data/cityvision.db and data/watchlist/stolen_vehicles.json
with 15 realistic, multi-camera vehicle trajectories and security alert scenarios.
Problem Statement ID: SIH26127
"""
import os
import sys
import sqlite3
import json
import time
import uuid
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "cityvision.db"
WATCHLIST_PATH = BASE_DIR / "data" / "watchlist" / "stolen_vehicles.json"
CAMERAS_PATH = BASE_DIR / "data" / "cameras" / "cameras.json"

# Load actual camera coordinates to ensure zero synthetic/hallucinated GPS
with open(CAMERAS_PATH, "r", encoding="utf-8") as f:
    CAMERAS = {c["id"]: c for c in json.load(f)}

# Base reference timestamp (1 hour ago so all data is fresh and active)
NOW = time.time()
T0 = NOW - 3600

# 15 Rich Vehicle Scenarios
FLEET_SPEC = [
    {
        "id": "GV-NCR-1001",
        "plate": "DL01AB1234",
        "class": "car",
        "flagged": 1,
        "hops": [
            ("CAM-001", 0, 101, 0.94),
            ("CAM-002", 280, 204, 0.96),
            ("CAM-005", 580, 502, 0.95),
        ],
        "description": "Stolen Honda City Sedan (Wanted under FIR #84920 / Crime Branch Alert)",
    },
    {
        "id": "GV-NCR-1002",
        "plate": "HR26DQ8890",
        "class": "suv",
        "flagged": 1,
        "hops": [
            ("CAM-004", 60, 401, 0.93),
            ("CAM-001", 135, 106, 0.95),
            ("CAM-002", 240, 208, 0.92),
        ],
        "description": "Black Mahindra Scorpio - Excessive Speed Violator (94.5 km/h in 50 km/h zone)",
    },
    {
        "id": "GV-NCR-1003",
        "plate": "UP16CD5521",
        "class": "truck",
        "flagged": 0,
        "hops": [
            ("CAM-003", 120, 302, 0.72),  # Partial occlusion on camera 3, resolved via Re-ID visual appearance
            ("CAM-002", 580, 214, 0.91),
            ("CAM-005", 1020, 509, 0.94),
        ],
        "description": "Commercial Container Carrier - Occluded Plate Re-ID Cross-Camera Match",
    },
    {
        "id": "GV-NCR-1004",
        "plate": "DL1PC9912",
        "class": "bus",
        "flagged": 0,
        "hops": [
            ("CAM-004", 0, 403, 0.95),
            ("CAM-001", 420, 110, 0.97),
            ("CAM-002", 840, 219, 0.96),
            ("CAM-005", 1320, 515, 0.94),
        ],
        "description": "DTC Electric Urban Transit Bus - Scheduled Arterial Route 44B",
    },
    {
        "id": "GV-NCR-1005",
        "plate": "MH02EE4311",
        "class": "car",
        "flagged": 0,
        "hops": [
            ("CAM-003", 300, 305, 0.91),
            ("CAM-002", 640, 222, 0.93),
            ("CAM-001", 990, 118, 0.95),
        ],
        "description": "Silver Hyundai Creta - Daily Tech Park Commuter",
    },
    {
        "id": "GV-NCR-1006",
        "plate": "DL3SBZ7719",
        "class": "motorcycle",
        "flagged": 0,
        "hops": [
            ("CAM-004", 450, 407, 0.89),
            ("CAM-003", 720, 310, 0.91),
            ("CAM-002", 1010, 228, 0.90),
        ],
        "description": "Express Logistics Two-Wheeler Courier Transit",
    },
    {
        "id": "GV-NCR-1007",
        "plate": "TEMP-2026-X",
        "class": "car",
        "flagged": 1,
        "hops": [
            ("CAM-001", 500, 122, 0.92),
            ("CAM-002", 810, 231, 0.94),
        ],
        "description": "Red Luxury Coupe - Expired Temporary Registration / Unregistered Plate",
    },
    {
        "id": "GV-NCR-1008",
        "plate": "DL1EAA1080",
        "class": "truck",
        "flagged": 0,
        "hops": [
            ("CAM-004", 180, 412, 0.96),
            ("CAM-001", 330, 125, 0.97),
            ("CAM-002", 520, 235, 0.98),
            ("CAM-005", 750, 522, 0.95),
        ],
        "description": "Emergency Medical Services / Hospital Critical Response Unit",
    },
    {
        "id": "GV-NCR-1009",
        "plate": "PB10FF8245",
        "class": "truck",
        "flagged": 0,
        "hops": [
            ("CAM-001", 200, 128, 0.93),
            ("CAM-004", 620, 418, 0.94),
            ("CAM-003", 1150, 318, 0.92),
        ],
        "description": "Inter-State Heavy Freight Logistics - Ring Road Bypass",
    },
    {
        "id": "GV-NCR-1010",
        "plate": "DL2CAV0001",
        "class": "car",
        "flagged": 0,
        "hops": [
            ("CAM-002", 800, 240, 0.97),
            ("CAM-005", 1120, 530, 0.98),
        ],
        "description": "Diplomatic VIP Transport - North Corridor to Airport Exit",
    },
    {
        "id": "GV-NCR-1011",
        "plate": "DL1TAY3344",
        "class": "car",
        "flagged": 0,
        "hops": [
            ("CAM-003", 100, 322, 0.95),
            ("CAM-004", 410, 424, 0.93),
            ("CAM-001", 720, 134, 0.96),
            ("CAM-002", 1050, 245, 0.94),
            ("CAM-005", 1400, 538, 0.97),
        ],
        "description": "Commercial Airport Cab - Full 5-Node City-Wide Transit Corridor",
    },
    {
        "id": "GV-NCR-1012",
        "plate": "HR26DK9988",
        "class": "suv",
        "flagged": 1,
        "hops": [
            ("CAM-004", 900, 430, 0.94),
            ("CAM-003", 1210, 328, 0.92),
        ],
        "description": "Hit and Run Suspect Vehicle (Flagged under NCR Inter-State Alert)",
    },
    {
        "id": "GV-NCR-1013",
        "plate": "DL1PB4400",
        "class": "bus",
        "flagged": 0,
        "hops": [
            ("CAM-003", 600, 335, 0.96),
            ("CAM-002", 950, 252, 0.95),
            ("CAM-001", 1310, 142, 0.97),
        ],
        "description": "Authorized School Transit Bus - Morning Return Run",
    },
    {
        "id": "GV-NCR-1014",
        "plate": "UP16XY5544",
        "class": "truck",
        "flagged": 1,
        "hops": [
            ("CAM-001", 400, 145, 0.91),
            ("CAM-002", 780, 258, 0.93),
            ("CAM-005", 1240, 545, 0.92),
        ],
        "description": "Commercial Toll Evasion / Impound Warrant Flagged Carrier",
    },
    {
        "id": "GV-TEST-1001",
        "plate": "RJ14AB1234",
        "class": "car",
        "flagged": 0,
        "hops": [
            ("CAM-001", 200, 150, 0.96),
            ("CAM-002", 550, 265, 0.95),
            ("CAM-005", 920, 550, 0.97),
        ],
        "description": "Rajasthan Inter-State Touring Vehicle - Verified Multi-Camera Transit",
    },
]


def seed_database():
    print(f"[1/3] Connecting to SQLite persistence: {DB_PATH}")
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure tables exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_vehicles (
            global_vehicle_id TEXT PRIMARY KEY,
            primary_plate TEXT,
            vehicle_class TEXT NOT NULL,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            total_observations INTEGER DEFAULT 1,
            total_cameras_visited INTEGER DEFAULT 1,
            is_flagged INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_observations (
            observation_id TEXT PRIMARY KEY,
            global_vehicle_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            local_track_id INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            latitude REAL,
            longitude REAL,
            plate_text TEXT,
            ocr_confidence REAL,
            reid_embedding_preview TEXT,
            confidence REAL DEFAULT 1.0,
            source_frame INTEGER DEFAULT 0,
            FOREIGN KEY (global_vehicle_id) REFERENCES global_vehicles (global_vehicle_id) ON DELETE CASCADE
        )
    """)

    # Clear old demo records to maintain pristine state
    cursor.execute("DELETE FROM vehicle_observations")
    cursor.execute("DELETE FROM global_vehicles")

    total_obs_inserted = 0
    total_vehs_inserted = 0

    for veh in FLEET_SPEC:
        gid = veh["id"]
        plate = veh["plate"]
        vclass = veh["class"]
        is_flagged = veh["flagged"]
        hops = veh["hops"]

        first_ts = T0 + hops[0][1]
        last_ts = T0 + hops[-1][1]
        cams_visited = len(set(h[0] for h in hops))
        total_obs = len(hops) * 2  # 2 frame observations per camera pass for high fidelity

        cursor.execute("""
            INSERT INTO global_vehicles (
                global_vehicle_id, primary_plate, vehicle_class,
                first_seen, last_seen, total_observations, total_cameras_visited,
                is_flagged, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            gid, plate, vclass,
            first_ts, last_ts, total_obs, cams_visited,
            is_flagged, first_ts, last_ts
        ))
        total_vehs_inserted += 1

        # Insert sequential georeferenced observations
        for hop_idx, (cam_id, offset_sec, track_id, conf) in enumerate(hops):
            cam = CAMERAS.get(cam_id, {})
            lat = cam.get("latitude", 28.6139)
            lng = cam.get("longitude", 77.2090)

            # Two observations per camera visit (entrance and exit)
            for sub_frame in range(2):
                obs_ts = T0 + offset_sec + (sub_frame * 3.5)
                obs_id = str(uuid.uuid4())
                reid_preview = json.dumps([
                    round(0.05 * (hop_idx + 1) + (sub_frame * 0.02) - 0.04, 4),
                    round(0.12 - 0.03 * (hop_idx + 1), 4),
                    round(0.08 * (sub_frame + 1), 4),
                    round(-0.05 + 0.01 * track_id, 4),
                    0.0912, -0.0421, 0.0634, 0.0155
                ])

                cursor.execute("""
                    INSERT INTO vehicle_observations (
                        observation_id, global_vehicle_id, camera_id, local_track_id,
                        timestamp, latitude, longitude, plate_text, ocr_confidence,
                        reid_embedding_preview, confidence, source_frame
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs_id, gid, cam_id, track_id,
                    obs_ts, lat, lng, plate, conf,
                    reid_preview, conf, 15 + sub_frame * 25
                ))
                total_obs_inserted += 1

    conn.commit()
    conn.close()
    print(f"[OK] Seeded {total_vehs_inserted} global vehicles and {total_obs_inserted} georeferenced observations.")


def update_watchlist():
    print(f"[2/3] Updating Watchlist registry: {WATCHLIST_PATH}")
    os.makedirs(WATCHLIST_PATH.parent, exist_ok=True)
    watchlist_entries = [
        {
            "plate_number": "DL01AB1234",
            "reason": "Wanted - Stolen Honda City (FIR #84920 Crime Branch)",
            "alert_level": "CRITICAL",
            "vehicle_type": "Sedan",
            "reported_date": "2026-09-01T10:00:00Z"
        },
        {
            "plate_number": "HR26DK9988",
            "reason": "Hit and run investigation suspect - NCR Traffic Notice",
            "alert_level": "CRITICAL",
            "vehicle_type": "SUV",
            "reported_date": "2026-09-03T14:30:00Z"
        },
        {
            "plate_number": "UP16XY5544",
            "reason": "Unpaid commercial toll evasion / Impound notice",
            "alert_level": "HIGH",
            "vehicle_type": "Truck",
            "reported_date": "2026-09-04T08:15:00Z"
        },
        {
            "plate_number": "TEMP-2026-X",
            "reason": "Expired temporary dealer permit - Unauthorized public transit",
            "alert_level": "HIGH",
            "vehicle_type": "Coupe",
            "reported_date": "2026-09-04T12:00:00Z"
        },
        {
            "plate_number": "RJ14AB1234",
            "reason": "Verified Demonstration Test Target (Inter-State Pass-Through)",
            "alert_level": "MEDIUM",
            "vehicle_type": "Sedan",
            "reported_date": "2026-09-05T06:00:00Z"
        }
    ]

    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist_entries, f, indent=2)
    print(f"[OK] Registered {len(watchlist_entries)} watchlist target entries.")


if __name__ == "__main__":
    seed_database()
    update_watchlist()
    print("[3/3] Demo data generation complete. All municipal surveillance records initialized.")
