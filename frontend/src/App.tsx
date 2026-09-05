import React, { useState, useEffect, useCallback } from 'react';
import type { ActiveTab, CameraNode, GlobalVehicle, AlertItem, TrafficMetrics } from './types';
import { Navbar } from './components/Navbar';
import { Dashboard } from './components/Dashboard';
import { LiveCameraView } from './components/LiveCameraView';
import { VehicleSearch } from './components/VehicleSearch';
import { VehicleDetails } from './components/VehicleDetails';
import { TrajectoryMap } from './components/TrajectoryMap';
import { AlertsPanel } from './components/AlertsPanel';
import { AnalyticsView } from './components/AnalyticsView';
import { DemoConsole } from './components/DemoConsole';
import { 
  fetchCameras, 
  fetchVehicles, 
  fetchAlerts, 
  fetchAnalytics,
  fetchSystemMode,
  updateSystemMode,
  connectTelemetryWebSocket,
} from './services/api';

// Baseline fallback camera nodes matching config/cameras.yaml (Jaipur grid)
const OFFLINE_SEED_CAMERAS: CameraNode[] = [
  {
    id: 'CAM-001',
    name: 'North Gateway Intersection',
    latitude: 28.6139,
    longitude: 77.2090,
    heading_deg: 45.0,
    fps: 15,
    source_type: 'file',
    stream_uri: 'data/sample_videos/cam_01.mp4',
    status: 'configured',
  },
  {
    id: 'CAM-002',
    name: 'Central Ring Road Eastbound',
    latitude: 28.6180,
    longitude: 77.2150,
    heading_deg: 90.0,
    fps: 15,
    source_type: 'file',
    stream_uri: 'data/sample_videos/cam_02.mp4',
    status: 'configured',
  },
  {
    id: 'CAM-003',
    name: 'South Metro Junction',
    latitude: 28.6090,
    longitude: 77.2120,
    heading_deg: 180.0,
    fps: 15,
    source_type: 'file',
    stream_uri: 'data/sample_videos/cam_03.mp4',
    status: 'configured',
  },
  {
    id: 'CAM-004',
    name: 'West Tech Park Avenue',
    latitude: 28.6145,
    longitude: 77.2020,
    heading_deg: 270.0,
    fps: 15,
    source_type: 'file',
    stream_uri: 'data/sample_videos/cam_04.mp4',
    status: 'configured',
  },
  {
    id: 'CAM-005',
    name: 'City Terminal Outer Exit',
    latitude: 28.6220,
    longitude: 77.2185,
    heading_deg: 120.0,
    fps: 15,
    source_type: 'file',
    stream_uri: 'data/sample_videos/cam_05.mp4',
    status: 'configured',
  },
];

const DEFAULT_METRICS: TrafficMetrics = {
  active_camera_count: 0,
  total_tracked_vehicles: 0,
  average_speed_kmh: 0.0,
  hourly_vehicle_counts: Array(24).fill(0),
  congestion_index_percent: 0.0,
};

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const [cameras, setCameras] = useState<CameraNode[]>(OFFLINE_SEED_CAMERAS);
  const [vehicles, setVehicles] = useState<GlobalVehicle[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [metrics, setMetrics] = useState<TrafficMetrics>(DEFAULT_METRICS);
  const [selectedCameraId, setSelectedCameraId] = useState<string>('CAM-001');
  const [selectedVehicle, setSelectedVehicle] = useState<GlobalVehicle | null>(null);
  
  const [systemMode, setSystemMode] = useState<'real' | 'demo'>('real');
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Synchronize data from backend API
  const loadBackendData = useCallback(async () => {
    setIsRefreshing(true);
    let backendReachable = true;

    try {
      const modeData = await fetchSystemMode();
      if (modeData && modeData.mode) {
        setSystemMode(modeData.mode);
      }
    } catch {
      // Backend may be offline
    }

    try {
      const camData = await fetchCameras();
      if (camData && camData.length > 0) {
        setCameras(camData);
      }
    } catch {
      backendReachable = false;
    }

    try {
      const vehData = await fetchVehicles(100);
      setVehicles(vehData);
      if (vehData.length > 0 && !selectedVehicle) {
        setSelectedVehicle(vehData[0]);
      }
    } catch {
      backendReachable = false;
    }

    try {
      const alertData = await fetchAlerts(50);
      setAlerts(alertData);
    } catch {
      backendReachable = false;
    }

    try {
      const metricData = await fetchAnalytics();
      setMetrics(metricData);
    } catch {
      backendReachable = false;
    }

    setIsDemoMode(!backendReachable);
    setIsRefreshing(false);
  }, [selectedVehicle]);

  // Initial load
  useEffect(() => {
    loadBackendData();
  }, [loadBackendData]);

  // Handle switching operational mode
  const handleToggleMode = async (newMode: 'real' | 'demo') => {
    setSystemMode(newMode);
    try {
      await updateSystemMode(newMode);
    } catch (e) {
      console.warn('Failed to switch operational mode on backend', e);
    }
    loadBackendData();
  };

  // Connect live WebSocket stream
  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      ws = connectTelemetryWebSocket((data) => {
        if (data.event === 'alert_updated' || data.event === 'alert_triggered') {
          fetchAlerts(50).then(setAlerts).catch(() => {});
        } else if (data.event === 'vehicle_detected') {
          fetchVehicles(100).then(setVehicles).catch(() => {});
        } else if (data.event === 'system_mode_changed' && data.mode) {
          setSystemMode(data.mode);
          loadBackendData();
        } else if (data.event === 'demo_stage_advanced' || data.event === 'demo_reset') {
          loadBackendData();
        }
      });
    } catch {
      // WebSocket offline in mock/demo mode
    }

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [loadBackendData]);

  const handleSelectVehicle = (veh: GlobalVehicle) => {
    setSelectedVehicle(veh);
  };

  const handleSelectCamera = (camId: string) => {
    setSelectedCameraId(camId);
  };

  return (
    <div className="app-container">
      {/* Top Municipal Intelligence Command Header */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        alertCount={alerts.filter(a => a.status === 'NEW' || a.status === 'active').length}
        isDemoMode={isDemoMode}
        systemMode={systemMode}
        onToggleMode={handleToggleMode}
        onRefresh={loadBackendData}
        isRefreshing={isRefreshing}
      />

      {/* Prominent Demo Mode Indicator Banner */}
      {systemMode === 'demo' && (
        <div className="demo-mode-strip font-mono text-xs">
          <span className="demo-strip-tag">[DEMO MODE ACTIVE]</span>
          <span>
            Operating in isolated demonstration sandbox (<code>data/cityvision_demo.db</code>). Demonstrating 11-stage pipeline across Camera 01 (North), Camera 02 (Central), and Camera 03 (South). Production records remain untouched.
          </span>
          <button 
            type="button" 
            className="demo-strip-switch-btn"
            onClick={() => handleToggleMode('real')}
          >
            Switch to Real Processing →
          </button>
        </div>
      )}

      {/* Demo Mode Notice Banner if Backend Offline */}
      {isDemoMode && systemMode !== 'demo' && (
        <div className="demo-mode-strip offline font-mono text-xs">
          <span>[OFFLINE NOTICE]</span>
          <span>
            FastAPI backend is currently offline. Operating on isolated local seed fixtures. Run <code>uvicorn backend.app.main:app --port 8000</code> to activate live telemetry.
          </span>
        </div>
      )}

      {/* Main Screen Viewport */}
      <main className="main-content-area" id="main-content">
        {activeTab === 'dashboard' && (
          <Dashboard
            cameras={cameras}
            vehicles={vehicles}
            alerts={alerts}
            metrics={metrics}
            onSelectCamera={handleSelectCamera}
            onSelectVehicle={handleSelectVehicle}
            onNavigate={setActiveTab}
            isDemoMode={systemMode === 'demo'}
          />
        )}

        {activeTab === 'cameras' && (
          <LiveCameraView
            cameras={cameras}
            selectedCameraId={selectedCameraId}
            onSelectCamera={handleSelectCamera}
          />
        )}

        {activeTab === 'search' && (
          <VehicleSearch
            vehicles={vehicles}
            onSelectVehicle={handleSelectVehicle}
            onNavigate={setActiveTab}
          />
        )}

        {activeTab === 'details' && (
          <VehicleDetails
            vehicle={selectedVehicle}
            onNavigate={setActiveTab}
          />
        )}

        {activeTab === 'map' && (
          <TrajectoryMap
            cameras={cameras}
            vehicles={vehicles}
            alerts={alerts}
            activeVehicle={selectedVehicle}
            onSelectVehicle={handleSelectVehicle}
            onSelectCamera={handleSelectCamera}
            onNavigate={setActiveTab}
            onCameraUpdated={(updated) => {
              setCameras((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
            }}
          />
        )}

        {activeTab === 'alerts' && (
          <AlertsPanel
            alerts={alerts}
            onRefreshAlerts={loadBackendData}
          />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsView
            metrics={metrics}
            cameras={cameras}
          />
        )}
      </main>

      {/* Interactive 11-Stage Demo Walkthrough Console */}
      {systemMode === 'demo' && (
        <DemoConsole
          onNavigate={setActiveTab}
          onRefreshData={loadBackendData}
          onSelectVehicle={handleSelectVehicle}
        />
      )}
    </div>
  );
};

export default App;
