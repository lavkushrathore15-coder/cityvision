import React from 'react';
import type { CameraNode, GlobalVehicle, AlertItem, TrafficMetrics, ActiveTab } from '../types';
import { 
  Cctv, 
  Car, 
  ShieldAlert, 
  Activity, 
  ArrowUpRight, 
  CheckCircle2, 
  Clock, 
} from 'lucide-react';

interface DashboardProps {
  cameras: CameraNode[];
  vehicles: GlobalVehicle[];
  alerts: AlertItem[];
  metrics: TrafficMetrics;
  onSelectCamera: (camId: string) => void;
  onSelectVehicle: (vehicle: GlobalVehicle) => void;
  onNavigate: (tab: ActiveTab) => void;
  isDemoMode?: boolean;
}

export const Dashboard: React.FC<DashboardProps> = ({
  cameras,
  vehicles,
  alerts,
  metrics,
  onSelectCamera,
  onSelectVehicle,
  onNavigate,
  isDemoMode = false,
}) => {
  const activeAlertsCount = alerts.filter(a => a.status === 'NEW' || a.status === 'active').length;
  const operationalCount = cameras.filter(c => c.status === 'configured' || c.status === 'streaming').length;
  const stageStatus = isDemoMode ? 'SIMULATED' : (cameras.length > 0 ? 'READY' : 'STANDBY');

  const pipelineStages = [
    { step: 'DETECT', name: '1. Ingestion & Vehicle Detection', model: 'OpenCV Stream Ingestion + YOLOv8 Multi-Class DNN', status: stageStatus, desc: `${cameras.length} CCTV camera feeds monitored` },
    { step: 'IDENTIFY', name: '2. License Plate ANPR & Re-ID', model: 'Morphological Filter + EasyOCR + YOLO Appearance Features', status: stageStatus, desc: 'Normalized plate text & 256-dim L2 appearance vectors' },
    { step: 'TRACK', name: '3. Cross-Camera Association', model: 'ByteTrack Kalman + Spatio-Temporal Fusion Matcher', status: stageStatus, desc: 'Intra-camera continuity & global vehicle ID correlation' },
    { step: 'UNDERSTAND', name: '4. Trajectory & Urban Analytics', model: 'PostGIS / SQLite Spatial LineString Topology', status: stageStatus, desc: 'Chronological route reconstruction & transit delay metrics' },
    { step: 'ACT', name: '5. Alerts & Watchlist Triggers', model: 'Blacklist Regex Matcher + Velocity Violation Engine', status: stageStatus, desc: 'Real-time incident dispatch for command operators' },
  ];

  const totalObservations = vehicles.reduce((acc, v) => acc + (v.waypoints ? v.waypoints.length : 1), 0);

  return (
    <div className="dashboard-container">
      {/* 1. SYSTEM OVERVIEW (KPIs) */}
      <div className="dashboard-section-header">
        <h2 className="dashboard-section-title">SYSTEM OVERVIEW</h2>
        <span className="dashboard-section-meta font-mono text-xs text-muted">
          Active Municipal CCTV Network &bull; Real-Time Telemetry
        </span>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card" onClick={() => onNavigate('cameras')} title="View all configured camera nodes">
          <div className="kpi-header">
            <span className="kpi-title">ACTIVE CAMERAS</span>
            <Cctv size={16} className="kpi-icon" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{operationalCount}</span>
            <span className="kpi-unit">/ {cameras.length} Nodes</span>
          </div>
          <div className="kpi-footer">
            <span className={operationalCount > 0 ? "text-emerald font-mono text-xs" : "text-muted font-mono text-xs"}>
              ● {operationalCount > 0 ? `${operationalCount} Feeds Active` : 'Offline'}
            </span>
            <ArrowUpRight size={13} />
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('search')} title="Total vehicle observations detected">
          <div className="kpi-header">
            <span className="kpi-title">VEHICLES DETECTED</span>
            <Activity size={16} className="kpi-icon" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{totalObservations}</span>
            <span className="kpi-unit">Observations</span>
          </div>
          <div className="kpi-footer">
            <span className="text-muted font-mono text-xs">Multi-Camera Detections</span>
            <ArrowUpRight size={13} />
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('search')} title="Unique global vehicle identities">
          <div className="kpi-header">
            <span className="kpi-title">TRACKED VEHICLES</span>
            <Car size={16} className="kpi-icon" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{metrics.total_tracked_vehicles || vehicles.length}</span>
            <span className="kpi-unit">Global Identities</span>
          </div>
          <div className="kpi-footer">
            <span className="text-muted font-mono text-xs">Avg Speed: {metrics.average_speed_kmh.toFixed(1)} km/h</span>
            <ArrowUpRight size={13} />
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('alerts')} title="Active security & traffic alerts">
          <div className="kpi-header">
            <span className="kpi-title">ACTIVE ALERTS</span>
            <ShieldAlert size={16} className={`kpi-icon ${activeAlertsCount > 0 ? 'text-red' : ''}`} />
          </div>
          <div className="kpi-main">
            <span className={`kpi-value ${activeAlertsCount > 0 ? 'text-red' : ''}`}>
              {activeAlertsCount}
            </span>
            <span className="kpi-unit">Pending Incidents</span>
          </div>
          <div className="kpi-footer">
            <span className="text-muted font-mono text-xs">{alerts.length} Total Recorded</span>
            <ArrowUpRight size={13} />
          </div>
        </div>
      </div>

      {/* 2. LIVE / RECENT CAMERA ACTIVITY STRIP */}
      <div className="panel-card" style={{ marginBottom: '1.25rem' }}>
        <div className="panel-header">
          <div className="panel-title-group">
            <Cctv size={16} className="text-blue" />
            <h2 className="panel-title">LIVE / RECENT CAMERA ACTIVITY</h2>
          </div>
          <button 
            type="button"
            className="btn-link" 
            onClick={() => onNavigate('cameras')}
          >
            Open All CCTV Feeds &rarr;
          </button>
        </div>

        {cameras.length === 0 ? (
          <div className="empty-state-compact">
            <Clock size={18} className="text-muted" />
            <span>No camera sensors currently configured.</span>
          </div>
        ) : (
          <div className="camera-activity-strip">
            {cameras.map((cam) => (
              <div 
                key={cam.id} 
                className="camera-activity-tile"
                onClick={() => {
                  onSelectCamera(cam.id);
                  onNavigate('cameras');
                }}
                title={`Click to view feed for ${cam.name}`}
              >
                <div className="camera-tile-header">
                  <span className="camera-id-badge font-mono">{cam.id}</span>
                  <span className="status-pill status-active">LIVE</span>
                </div>
                <div className="camera-tile-name">{cam.name}</div>
                <div className="camera-tile-meta font-mono text-xs text-muted">
                  {cam.latitude.toFixed(4)}°N, {cam.longitude.toFixed(4)}°E &bull; {cam.fps} FPS
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main 2-Column Dashboard Body */}
      <div className="dashboard-columns">
        {/* Left Column: Recent Passes & Pipeline State */}
        <div className="dashboard-col">
          {/* Recent Multi-Camera Passes */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <Car size={16} />
                <h2 className="panel-title">Recent Correlated Vehicle Passes</h2>
                {isDemoMode && <span className="demo-badge-isolated font-mono">[DEMO DATA]</span>}
              </div>
              <button 
                type="button"
                className="btn-link" 
                onClick={() => onNavigate('search')}
              >
                Search Database &rarr;
              </button>
            </div>

            {vehicles.length === 0 ? (
              <div className="empty-state-compact">
                <Clock size={20} className="text-muted" />
                <p>No vehicle observations recorded in current session.</p>
              </div>
            ) : (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>GLOBAL VEHICLE ID</th>
                      <th>LICENSE PLATE</th>
                      <th>CLASS</th>
                      <th>CAMERAS PASSED</th>
                      <th>LAST SEEN</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vehicles.slice(0, 5).map((veh) => (
                      <tr key={veh.global_id} className={veh.is_flagged ? 'row-flagged' : ''}>
                        <td className="font-mono text-bold">{veh.global_id}</td>
                        <td>
                          {veh.primary_plate ? (
                            <span className="plate-badge">{veh.primary_plate}</span>
                          ) : (
                            <span className="text-muted">Unreadable</span>
                          )}
                        </td>
                        <td>
                          <span className="badge badge-class">{veh.vehicle_class.toUpperCase()}</span>
                        </td>
                        <td className="text-center">{veh.total_cameras_passed} Nodes</td>
                        <td className="font-mono text-muted text-sm">
                          {veh.last_seen.substring(11, 19)} UTC
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-action-small"
                            onClick={() => {
                              onSelectVehicle(veh);
                              onNavigate('details');
                            }}
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* AI Subsystem Pipeline Architecture */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <Activity size={16} />
                <h2 className="panel-title">End-to-End Pipeline Health</h2>
              </div>
              <span className="badge badge-online">ALL SUBSYSTEMS READY</span>
            </div>

            <div className="pipeline-list">
              {pipelineStages.map((stage, idx) => (
                <div key={idx} className="pipeline-item">
                  <div className="pipeline-indicator">
                    <CheckCircle2 size={14} className="text-emerald" />
                  </div>
                  <div className="pipeline-details">
                    <div className="pipeline-header-row">
                      <span className="badge badge-step font-mono">{stage.step}</span>
                      <span className="pipeline-name">{stage.name}</span>
                      <span className="pipeline-model font-mono">{stage.model}</span>
                    </div>
                    <span className="pipeline-desc">{stage.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Sensor Network & Active Incidents */}
        <div className="dashboard-col">
          {/* CCTV Grid Status */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <Cctv size={16} />
                <h2 className="panel-title">Camera Sensor Network</h2>
              </div>
              <button 
                type="button"
                className="btn-link" 
                onClick={() => onNavigate('cameras')}
              >
                View Feeds &rarr;
              </button>
            </div>

            <div className="camera-status-list">
              {cameras.map((cam) => (
                <div 
                  key={cam.id} 
                  className="camera-status-row"
                  onClick={() => {
                    onSelectCamera(cam.id);
                    onNavigate('cameras');
                  }}
                >
                  <div className="camera-meta">
                    <div className="camera-row-title">
                      <span className="camera-id-badge font-mono">{cam.id}</span>
                      <span className="camera-name">{cam.name}</span>
                    </div>
                    <span className="camera-coord font-mono">
                      {cam.latitude.toFixed(4)}°N, {cam.longitude.toFixed(4)}°E ({cam.fps} FPS)
                    </span>
                  </div>
                  <div className="camera-actions">
                    <span className="status-pill status-active">LIVE</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Active Alerts */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <ShieldAlert size={16} className="text-red" />
                <h2 className="panel-title">Operational Incident Feed</h2>
                {isDemoMode && <span className="demo-badge-isolated font-mono">[DEMO DATA]</span>}
              </div>
              <button 
                type="button"
                className="btn-link" 
                onClick={() => onNavigate('alerts')}
              >
                All Alerts &rarr;
              </button>
            </div>

            {alerts.length === 0 ? (
              <div className="empty-state-compact">
                <CheckCircle2 size={20} className="text-emerald" />
                <p>No active security or traffic alerts detected.</p>
              </div>
            ) : (
              <div className="alert-list-compact">
                {alerts.slice(0, 4).map((alert) => (
                  <div 
                    key={alert.id || alert.alert_id} 
                    className={`alert-item-compact severity-${alert.severity.toLowerCase()}`}
                    onClick={() => onNavigate('alerts')}
                  >
                    <div className="alert-compact-header">
                      <span className={`badge badge-severity-${alert.severity.toLowerCase()}`}>
                        {alert.severity}
                      </span>
                      <span className="font-mono text-muted text-xs">
                        {alert.timestamp_iso.substring(11, 19)} UTC
                      </span>
                    </div>
                    <p className="alert-compact-msg">{alert.message}</p>
                    <div className="alert-compact-meta font-mono text-xs">
                      <span>CAM: {alert.camera_id}</span>
                      {alert.plate_text && <span>PLATE: {alert.plate_text}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
