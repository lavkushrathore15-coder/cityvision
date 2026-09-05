// CITYVISION AI - Comprehensive TypeScript Type Definitions
// Problem Statement ID: SIH26127

export type ActiveTab = 
  | 'dashboard'
  | 'cameras'
  | 'search'
  | 'details'
  | 'map'
  | 'alerts'
  | 'analytics';

export interface CameraNode {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  heading_deg: number;
  fps: number;
  source_type: string;
  stream_uri: string;
  status: 'configured' | 'streaming' | 'offline' | 'error';
  active_track_count?: number;
}

export interface CameraStatus {
  camera_id: string;
  camera_name: string;
  source_uri: string;
  source_type: string;
  is_connected: boolean;
  processing_status: string;
  total_frames: number;
  frames_read: number;
  frames_sampled: number;
  fps: number;
  resolution: {
    width: number;
    height: number;
  };
  location: {
    latitude: number | null;
    longitude: number | null;
    description: string;
    is_gps_available: boolean;
    source: string;
  };
  error_message?: string | null;
}

export interface TrajectoryWaypoint {
  camera_id: string;
  camera_name: string;
  latitude: number;
  longitude: number;
  timestamp_iso: string;
  speed_estimate_kmh?: number;
  confidence: number;
}

export interface CameraVisit {
  camera_id: string;
  camera_name: string;
  arrival_time: number;
  departure_time: number;
  arrival_iso: string;
  departure_iso: string;
  duration_sec: number;
  observation_count: number;
  plate_reads: string[];
  location: {
    latitude: number;
    longitude: number;
  } | null;
}

export interface CameraMovement {
  from_camera_id: string;
  to_camera_id: string;
  departure_time: number;
  arrival_time: number;
  elapsed_time_sec: number;
  distance_meters: number | null;
  speed_kmh: number | null;
  is_feasible: boolean;
}

export interface GlobalVehicle {
  global_id: string;
  primary_plate?: string | null;
  vehicle_class: string;
  first_seen: string;
  last_seen: string;
  total_cameras_passed: number;
  waypoints: TrajectoryWaypoint[];
  is_flagged: boolean;
}

export interface VehicleTimeline {
  global_vehicle_id: string;
  primary_plate: string | null;
  vehicle_class: string;
  first_seen: string;
  last_seen: string;
  total_cameras_visited: number;
  total_observations: number;
  is_flagged: boolean;
  flag_reason?: string | null;
  camera_visits: CameraVisit[];
  movements: CameraMovement[];
}

export interface ObservationDetail {
  observation_id: string;
  global_vehicle_id: string;
  camera_id: string;
  camera_name?: string;
  local_track_id: number;
  frame_number: number;
  timestamp: number;
  timestamp_iso: string;
  location: { latitude: number; longitude: number } | null;
  bounding_box: { x1: number; y1: number; x2: number; y2: number };
  detection_confidence: number;
  plate_text?: string | null;
  ocr_confidence?: number | null;
  reid_preview?: string | null;
  source_frame_uri?: string | null;
}

export interface AlertItem {
  id: string;
  alert_id?: string;
  alert_type: string; // "WATCHLIST_HIT", "SPEED_VIOLATION", "UNUSUAL_TRANSIT"
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO' | 'WARNING';
  camera_id: string;
  global_vehicle_id?: string | null;
  plate_text?: string | null;
  message: string;
  timestamp_iso: string;
  details?: Record<string, any>;
  status: 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED' | 'active' | 'acknowledged' | 'resolved';
  acknowledged_by?: string | null;
}

export interface TrafficCounts {
  total_tracked_vehicles: number;
  active_camera_count: number;
  hourly_vehicle_counts: number[];
  total_observations_recorded: number;
  time_window_start_iso: string;
  time_window_end_iso: string;
}

export interface CameraActivityItem {
  camera_id: string;
  camera_name: string;
  total_observations: number;
  unique_vehicles_observed: number;
  last_observation_timestamp: string | null;
  status: string;
}

export interface ZoneDensityItem {
  camera_id: string;
  zone_name: string;
  latitude: number | null;
  longitude: number | null;
  active_vehicle_density: number;
  density_level: 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE';
}

export interface CongestionItem {
  from_camera_id: string;
  to_camera_id: string;
  corridor_name: string;
  distance_meters: number | null;
  recorded_transits: number;
  average_transit_speed_kmh: number | null;
  free_flow_speed_kmh: number;
  congestion_level: 'FREE_FLOW' | 'MODERATE' | 'CONGESTED' | 'HEAVY_CONGESTION';
  delay_ratio: number;
}

export interface TrafficMetrics {
  active_camera_count: number;
  total_tracked_vehicles: number;
  average_speed_kmh: number;
  hourly_vehicle_counts: number[];
  congestion_index_percent: number;
}

export interface CameraLocationUpdateRequest {
  latitude: number | null;
  longitude: number | null;
  heading_deg?: number | null;
  description?: string | null;
}

export interface GisFilters {
  time_range_preset: '15m' | '1h' | '6h' | '24h' | 'ALL';
  camera_id: string;
  vehicle_id: string;
  alert_type: string;
  start_time?: number | null;
  end_time?: number | null;
}

export interface GisSummaryData {
  cameras: Array<CameraNode & { is_gps_available: boolean }>;
  trajectories: Array<{
    global_id: string;
    primary_plate: string | null;
    vehicle_class: string;
    first_seen: string;
    last_seen: string;
    first_seen_timestamp: number;
    last_seen_timestamp: number;
    is_spatial_available: boolean;
    visited_cameras: string[];
    total_distance_meters: number | null;
    waypoints: Array<{
      camera_id: string;
      timestamp: number;
      timestamp_iso: string;
      latitude: number | null;
      longitude: number | null;
      is_gps_available: boolean;
      plate_text: string | null;
      confidence: number;
    }>;
    polyline: [number, number][];
    movements: Array<{
      from_camera_id: string;
      to_camera_id: string;
      departure_time: number;
      arrival_time: number;
      elapsed_time_sec: number;
      distance_meters: number | null;
      speed_kmh: number | null;
      is_feasible: boolean;
    }>;
  }>;
  corridors: CongestionItem[];
  zones: ZoneDensityItem[];
  alerts: Array<{
    alert_id: string;
    alert_type: string;
    severity: string;
    camera_id: string;
    camera_name: string;
    global_vehicle_id: string | null;
    plate_text: string | null;
    message: string;
    timestamp_iso: string;
    status: string;
    latitude: number | null;
    longitude: number | null;
    is_gps_available: boolean;
  }>;
  unconfigured_camera_count: number;
  total_cameras: number;
  filter_applied: Record<string, any>;
}

export interface DemoStageProgress {
  stage: number;
  title: string;
  subtitle: string;
  camera_id: string;
  status: 'COMPLETED' | 'ACTIVE' | 'PENDING';
}

export interface DemoStatusResponse {
  is_demo_active: boolean;
  current_stage: number;
  total_stages: number;
  stage_info: {
    stage: number;
    title: string;
    subtitle: string;
    camera_id: string;
    camera_name: string;
    description: string;
    provenance: {
      source?: string;
      model_identifier?: string;
      dimension?: number;
      metric?: string;
      data_origin?: string;
      is_live_model_output?: boolean;
      rule_applied?: string;
      [key: string]: any;
    };
  };
  stages_progress: DemoStageProgress[];
  virtual_cameras: CameraNode[];
  active_vehicle: GlobalVehicle | null;
  trajectory: any;
  alerts: AlertItem[];
  history_log: Array<{
    stage: number;
    timestamp: number;
    event: string;
    camera_id?: string;
    details?: string;
    provenance?: string;
    [key: string]: any;
  }>;
  database_file: string;
  data_label: string;
}

export interface SystemModeResponse {
  mode: 'real' | 'demo';
  is_demo: boolean;
  database_file: string;
  demo_active: boolean;
  current_stage: number;
  total_stages: number;
}

