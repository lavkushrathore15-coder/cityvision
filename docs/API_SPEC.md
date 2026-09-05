# CITYVISION AI — REST & WebSocket API Specification

## Base URL
`http://localhost:8000/api/v1`

---

## 1. System Endpoints

### `GET /health`
Returns system status, active inference engine, and uptime.
- **Response `200 OK`**:
  ```json
  {
    "status": "online",
    "app": "CITYVISION AI",
    "environment": "development",
    "inference_device": "cpu"
  }
  ```

---

## 2. Camera Nodes

### `GET /cameras`
Returns all registered virtual and physical CCTV nodes.
- **Response `200 OK`**: List of `CameraResponse` objects.

### `GET /cameras/{camera_id}`
Returns metadata and status for a single camera.

---

## 3. Vehicles & Trajectories

### `GET /vehicles?limit=50`
Lists recently tracked vehicles with global tracking identifiers.

### `GET /vehicles/{global_id}/trajectory`
Retrieves chronological waypoints and camera traversal for a vehicle.

### `GET /vehicles/search?plate={plate_query}`
Searches historical detections by full or partial license plate text.

---

## 4. Alerts

### `GET /alerts?limit=50`
Lists active operational alerts (watchlist triggers, speeding, wrong-way driving).

---

## 5. Analytics

### `GET /analytics/traffic`
Returns aggregate traffic statistics:
- Active camera count
- Tracked vehicle count
- Average speed
- Hourly volume histogram
- Congestion index

---

## 6. Live Telemetry WebSocket

### `WS /ws/telemetry`
Bi-directional real-time feed streaming detection events, active tracking vectors, and incident alerts.
