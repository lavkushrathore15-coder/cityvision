// CITYVISION AI - Full API Client & WebSocket Telemetry Service
// Problem Statement ID: SIH26127

import type {
  CameraNode,
  CameraStatus,
  GlobalVehicle,
  VehicleTimeline,
  ObservationDetail,
  CameraMovement,
  AlertItem,
  TrafficCounts,
  CameraActivityItem,
  ZoneDensityItem,
  CongestionItem,
  TrafficMetrics,
  CameraLocationUpdateRequest,
  GisFilters,
  GisSummaryData,
  SystemModeResponse,
  DemoStatusResponse,
} from '../types';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' && window.location.origin
    ? `${window.location.origin}/api/v1`
    : 'http://localhost:8000/api/v1');

async function handleResponse<T>(res: Response, errorMessage: string): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || err.error || detail;
    } catch {
      // JSON parse fallback
    }
    throw new Error(`${errorMessage}: ${detail}`);
  }
  return res.json();
}

// ============================================================================
// CAMERAS
// ============================================================================
export async function fetchCameras(): Promise<CameraNode[]> {
  const res = await fetch(`${API_BASE_URL}/cameras`);
  return handleResponse<CameraNode[]>(res, 'Failed to fetch cameras');
}

export async function fetchCameraMetadata(id: string): Promise<CameraNode> {
  const res = await fetch(`${API_BASE_URL}/cameras/${encodeURIComponent(id)}`);
  return handleResponse<CameraNode>(res, `Failed to fetch camera ${id}`);
}

export async function fetchCameraStatus(id: string): Promise<CameraStatus> {
  const res = await fetch(`${API_BASE_URL}/cameras/${encodeURIComponent(id)}/status`);
  return handleResponse<CameraStatus>(res, `Failed to fetch status for camera ${id}`);
}

export interface DemoVideoAsset {
  filename: string;
  camera_id: string;
  path: string;
  url: string;
  size_bytes?: number;
}

export function getCameraStreamUrl(cameraId: string, overlay = true): string {
  return `${API_BASE_URL}/cameras/${encodeURIComponent(cameraId)}/stream?overlay=${overlay}`;
}

export function getCameraVideoUrl(cameraId: string): string {
  return `${API_BASE_URL}/cameras/${encodeURIComponent(cameraId)}/video`;
}

export function getLocalDemoVideoUrl(cameraId: string): string {
  const numStr = cameraId.replace(/\D/g, '');
  const num = parseInt(numStr, 10) || 1;
  const clampedNum = Math.min(Math.max(num, 1), 5);
  const formatted = clampedNum.toString().padStart(2, '0');
  return `/demo_videos/cam_${formatted}.mp4?v=h264_v3`;
}

export async function fetchDemoVideos(): Promise<{ status: string; videos: DemoVideoAsset[]; total: number }> {
  try {
    const res = await fetch(`${API_BASE_URL}/demo-videos`);
    return await handleResponse<{ status: string; videos: DemoVideoAsset[]; total: number }>(
      res,
      'Failed to fetch demo videos'
    );
  } catch {
    // Client-side fallback if backend is offline or custom port
    return {
      status: 'fallback',
      total: 5,
      videos: [1, 2, 3, 4, 5].map((idx) => {
        const id = `CAM-${idx.toString().padStart(3, '0')}`;
        const name = `cam_${idx.toString().padStart(2, '0')}.mp4`;
        return {
          filename: name,
          camera_id: id,
          path: `data/sample_videos/${name}`,
          url: `/demo_videos/${name}`,
        };
      }),
    };
  }
}

// ============================================================================
// VEHICLES
// ============================================================================
export async function fetchVehicles(limit = 50): Promise<GlobalVehicle[]> {
  const res = await fetch(`${API_BASE_URL}/vehicles?limit=${limit}`);
  return handleResponse<GlobalVehicle[]>(res, 'Failed to fetch vehicles');
}

export interface VehicleSearchParams {
  plate?: string;
  vehicle_class?: string;
  camera_id?: string;
  start_time?: number;
  end_time?: number;
  limit?: number;
}

export async function searchVehicles(params: VehicleSearchParams): Promise<GlobalVehicle[]> {
  const query = new URLSearchParams();
  if (params.plate) query.append('plate', params.plate);
  if (params.vehicle_class) query.append('vehicle_class', params.vehicle_class);
  if (params.camera_id) query.append('camera_id', params.camera_id);
  if (params.start_time) query.append('start_time', params.start_time.toString());
  if (params.end_time) query.append('end_time', params.end_time.toString());
  if (params.limit) query.append('limit', params.limit.toString());

  const res = await fetch(`${API_BASE_URL}/vehicles/search?${query.toString()}`);
  return handleResponse<GlobalVehicle[]>(res, 'Failed to search vehicles');
}

export async function fetchVehicleDetails(id: string): Promise<GlobalVehicle> {
  const res = await fetch(`${API_BASE_URL}/vehicles/${encodeURIComponent(id)}`);
  return handleResponse<GlobalVehicle>(res, `Failed to fetch vehicle ${id}`);
}

export async function fetchVehicleTimeline(id: string): Promise<VehicleTimeline> {
  const res = await fetch(`${API_BASE_URL}/vehicles/${encodeURIComponent(id)}/history`);
  return handleResponse<VehicleTimeline>(res, `Failed to fetch history for vehicle ${id}`);
}

export async function fetchTrajectory(globalId: string): Promise<GlobalVehicle> {
  const res = await fetch(`${API_BASE_URL}/vehicles/${encodeURIComponent(globalId)}/trajectory`);
  return handleResponse<GlobalVehicle>(res, `Failed to fetch trajectory for ${globalId}`);
}

export async function fetchMovements(globalId: string): Promise<CameraMovement[]> {
  const res = await fetch(`${API_BASE_URL}/trajectories/${encodeURIComponent(globalId)}/movements`);
  return handleResponse<CameraMovement[]>(res, `Failed to fetch movements for ${globalId}`);
}

// ============================================================================
// OBSERVATIONS
// ============================================================================
export async function fetchObservation(id: string): Promise<ObservationDetail> {
  const res = await fetch(`${API_BASE_URL}/observations/${encodeURIComponent(id)}`);
  return handleResponse<ObservationDetail>(res, `Failed to fetch observation ${id}`);
}

// ============================================================================
// ALERTS
// ============================================================================
export async function fetchAlerts(
  limit = 50,
  status?: string,
  severity?: string
): Promise<AlertItem[]> {
  const query = new URLSearchParams({ limit: limit.toString() });
  if (status) query.append('status', status);
  if (severity) query.append('severity', severity);

  const res = await fetch(`${API_BASE_URL}/alerts?${query.toString()}`);
  return handleResponse<AlertItem[]>(res, 'Failed to fetch alerts');
}

export async function fetchAlertDetails(id: string): Promise<AlertItem> {
  const res = await fetch(`${API_BASE_URL}/alerts/${encodeURIComponent(id)}`);
  return handleResponse<AlertItem>(res, `Failed to fetch alert ${id}`);
}

export async function updateAlertStatus(
  id: string,
  status: string,
  acknowledged_by?: string
): Promise<AlertItem> {
  const res = await fetch(`${API_BASE_URL}/alerts/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, acknowledged_by: acknowledged_by || 'Command_Operator' }),
  });
  return handleResponse<AlertItem>(res, `Failed to update alert ${id}`);
}

// ============================================================================
// ANALYTICS
// ============================================================================
export async function fetchAnalytics(): Promise<TrafficMetrics> {
  const res = await fetch(`${API_BASE_URL}/analytics/traffic`);
  return handleResponse<TrafficMetrics>(res, 'Failed to fetch traffic metrics');
}

export async function fetchTrafficCounts(): Promise<TrafficCounts> {
  const res = await fetch(`${API_BASE_URL}/analytics/traffic-counts`);
  return handleResponse<TrafficCounts>(res, 'Failed to fetch traffic counts');
}

export async function fetchCameraActivity(): Promise<{ cameras: CameraActivityItem[]; most_active_camera_id: string | null }> {
  const res = await fetch(`${API_BASE_URL}/analytics/camera-activity`);
  return handleResponse<{ cameras: CameraActivityItem[]; most_active_camera_id: string | null }>(
    res,
    'Failed to fetch camera activity'
  );
}

export async function fetchZoneDensity(): Promise<{ zones: ZoneDensityItem[]; city_average_density: number }> {
  const res = await fetch(`${API_BASE_URL}/analytics/zone-density`);
  return handleResponse<{ zones: ZoneDensityItem[]; city_average_density: number }>(
    res,
    'Failed to fetch zone density'
  );
}

export async function fetchCongestion(): Promise<{ corridors: CongestionItem[]; citywide_congestion_index_percent: number }> {
  const res = await fetch(`${API_BASE_URL}/analytics/congestion`);
  return handleResponse<{ corridors: CongestionItem[]; citywide_congestion_index_percent: number }>(
    res,
    'Failed to fetch congestion indicators'
  );
}

export async function updateCameraLocation(
  cameraId: string,
  data: CameraLocationUpdateRequest
): Promise<CameraNode> {
  const res = await fetch(`${API_BASE_URL}/cameras/${cameraId}/location`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<CameraNode>(res, `Failed to update camera ${cameraId} location`);
}

export async function fetchGisSummary(filters?: Partial<GisFilters>): Promise<GisSummaryData> {
  const params = new URLSearchParams();
  if (filters?.camera_id && filters.camera_id !== 'ALL') {
    params.set('camera_id', filters.camera_id);
  }
  if (filters?.vehicle_id) {
    params.set('vehicle_id', filters.vehicle_id);
  }
  if (filters?.alert_type && filters.alert_type !== 'ALL') {
    params.set('alert_type', filters.alert_type);
  }
  if (filters?.start_time) {
    params.set('start_time', filters.start_time.toString());
  }
  if (filters?.end_time) {
    params.set('end_time', filters.end_time.toString());
  }

  const qs = params.toString();
  const url = `${API_BASE_URL}/trajectories/gis-summary${qs ? `?${qs}` : ''}`;
  const res = await fetch(url);
  return handleResponse<GisSummaryData>(res, 'Failed to fetch GIS summary');
}

// ============================================================================
// WEBSOCKET TELEMETRY
// ============================================================================
export function connectTelemetryWebSocket(
  onMessage: (data: any) => void,
  onError?: (err: Event) => void
): WebSocket {
  let wsUrl = '';
  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/ws/dashboard';
  } else if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsUrl = `${proto}//${window.location.host}${API_BASE_URL}/ws/dashboard`;
  } else {
    wsUrl = 'ws://localhost:8000/api/v1/ws/dashboard';
  }
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.warn('Failed to parse WebSocket message', e);
    }
  };

  if (onError) {
    ws.onerror = onError;
  }

  return ws;
}

// ============================================================================
// SYSTEM MODE & DEMO PIPELINE CONTROLS
// ============================================================================
export async function fetchSystemMode(): Promise<SystemModeResponse> {
  const res = await fetch(`${API_BASE_URL}/system/mode`);
  return handleResponse<SystemModeResponse>(res, 'Failed to fetch operational mode');
}

export async function updateSystemMode(mode: 'real' | 'demo'): Promise<SystemModeResponse> {
  const res = await fetch(`${API_BASE_URL}/system/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  return handleResponse<SystemModeResponse>(res, `Failed to switch operational mode to ${mode}`);
}

export async function fetchDemoStatus(): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/demo/status`);
  return handleResponse<DemoStatusResponse>(res, 'Failed to fetch demo pipeline telemetry');
}

export async function startDemo(): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/demo/start`, { method: 'POST' });
  return handleResponse<DemoStatusResponse>(res, 'Failed to start demo pipeline');
}

export async function stepDemo(stage?: number): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/demo/step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stage !== undefined ? { stage } : {}),
  });
  return handleResponse<DemoStatusResponse>(res, 'Failed to step demo pipeline');
}

export async function resetDemo(): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/demo/reset`, { method: 'POST' });
  return handleResponse<DemoStatusResponse>(res, 'Failed to reset demo pipeline');
}

export async function runFullDemo(): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/demo/full`, { method: 'POST' });
  return handleResponse<DemoStatusResponse>(res, 'Failed to run full demo pipeline');
}
