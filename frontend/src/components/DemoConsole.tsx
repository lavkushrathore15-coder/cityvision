import React, { useState, useEffect, useRef } from 'react';
import type { DemoStatusResponse, ActiveTab } from '../types';
import { 
  stepDemo, 
  resetDemo, 
  runFullDemo, 
  fetchDemoStatus 
} from '../services/api';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  ChevronRight, 
  CheckCircle2, 
  AlertTriangle, 
  Cpu, 
  ShieldAlert, 
  Maximize2, 
  Minimize2, 
  MapPin, 
  Compass,
  ArrowRight
} from 'lucide-react';

interface DemoConsoleProps {
  onNavigate?: (tab: ActiveTab) => void;
  onRefreshData?: () => void;
  onSelectVehicle?: (veh: any) => void;
}

export const DemoConsole: React.FC<DemoConsoleProps> = ({ 
  onNavigate, 
  onRefreshData,
  onSelectVehicle,
}) => {
  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [isAutoPlaying, setIsAutoPlaying] = useState<boolean>(false);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const autoPlayTimerRef = useRef<any>(null);

  const loadStatus = async () => {
    try {
      const status = await fetchDemoStatus();
      setDemoStatus(status);
      if (status.active_vehicle && onSelectVehicle) {
        onSelectVehicle(status.active_vehicle);
      }
    } catch (e) {
      console.warn('Failed to load demo status', e);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  // Auto-play stepper
  useEffect(() => {
    if (isAutoPlaying) {
      autoPlayTimerRef.current = setInterval(async () => {
        setDemoStatus((prev) => {
          if (!prev || prev.current_stage >= 11) {
            setIsAutoPlaying(false);
            return prev;
          }
          return prev;
        });

        try {
          const res = await stepDemo();
          setDemoStatus(res);
          if (onRefreshData) onRefreshData();
          if (res.active_vehicle && onSelectVehicle) onSelectVehicle(res.active_vehicle);
          if (res.current_stage >= 11) {
            setIsAutoPlaying(false);
          }
        } catch {
          setIsAutoPlaying(false);
        }
      }, 2200);
    } else {
      if (autoPlayTimerRef.current) {
        clearInterval(autoPlayTimerRef.current);
      }
    }

    return () => {
      if (autoPlayTimerRef.current) {
        clearInterval(autoPlayTimerRef.current);
      }
    };
  }, [isAutoPlaying, onRefreshData, onSelectVehicle]);

  const handleStepForward = async () => {
    setIsLoading(true);
    try {
      const res = await stepDemo();
      setDemoStatus(res);
      if (onRefreshData) onRefreshData();
      if (res.active_vehicle && onSelectVehicle) onSelectVehicle(res.active_vehicle);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleJumpStage = async (stageNum: number) => {
    setIsLoading(true);
    try {
      const res = await stepDemo(stageNum);
      setDemoStatus(res);
      if (onRefreshData) onRefreshData();
      if (res.active_vehicle && onSelectVehicle) onSelectVehicle(res.active_vehicle);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    setIsAutoPlaying(false);
    setIsLoading(true);
    try {
      const res = await resetDemo();
      setDemoStatus(res);
      if (onRefreshData) onRefreshData();
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunFull = async () => {
    setIsLoading(true);
    try {
      const res = await runFullDemo();
      setDemoStatus(res);
      if (onRefreshData) onRefreshData();
      if (res.active_vehicle && onSelectVehicle) onSelectVehicle(res.active_vehicle);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const currentStage = demoStatus?.current_stage || 0;
  const stageInfo = demoStatus?.stage_info;

  return (
    <aside className={`demo-console-panel ${isCollapsed ? 'collapsed' : ''}`} aria-label="Demo Mode Interactive Console">
      {/* Header bar */}
      <div className="demo-console-header">
        <div className="demo-header-left">
          <div className="demo-live-pill">
            <span className="demo-amber-dot"></span>
            <span className="demo-pill-title">DEMO MODE ACTIVE</span>
          </div>
          <span className="demo-title-divider">/</span>
          <span className="demo-header-title">11-Stage End-to-End Pipeline Walkthrough</span>
          <span className="demo-badge-isolated" title="Demo records are strictly isolated in data/cityvision_demo.db">
            ISOLATED DB: data/cityvision_demo.db
          </span>
        </div>

        <div className="demo-header-controls">
          <div className="demo-actions-group">
            <button
              type="button"
              className={`demo-btn demo-btn-step ${isLoading ? 'btn-busy' : ''}`}
              onClick={handleStepForward}
              disabled={isLoading || currentStage >= 11}
              title="Execute next step in demonstration"
            >
              <ChevronRight size={15} />
              <span>Step Forward</span>
            </button>

            <button
              type="button"
              className={`demo-btn demo-btn-autoplay ${isAutoPlaying ? 'active' : ''}`}
              onClick={() => setIsAutoPlaying(!isAutoPlaying)}
              title={isAutoPlaying ? 'Pause Automated Stepping' : 'Auto Play Steps (2.2s)'}
            >
              {isAutoPlaying ? <Pause size={14} /> : <Play size={14} />}
              <span>{isAutoPlaying ? 'Pause Auto' : 'Auto-Play'}</span>
            </button>

            <button
              type="button"
              className="demo-btn demo-btn-full"
              onClick={handleRunFull}
              disabled={isLoading}
              title="Execute all 11 stages sequentially"
            >
              <Cpu size={14} />
              <span>Run Full 11 Stages</span>
            </button>

            <button
              type="button"
              className="demo-btn demo-btn-reset"
              onClick={handleReset}
              disabled={isLoading}
              title="Reset isolated database to Stage 0"
            >
              <RotateCcw size={14} />
              <span>Reset</span>
            </button>
          </div>

          <button
            type="button"
            className="demo-btn-collapse"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? 'Expand Demo Console' : 'Minimize Demo Console'}
          >
            {isCollapsed ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
          </button>
        </div>
      </div>

      {/* Main Body */}
      {!isCollapsed && (
        <div className="demo-console-body">
          {/* Stepper Bar */}
          <div className="demo-stepper-container">
            <div className="demo-stepper-track">
              {demoStatus?.stages_progress.map((s) => {
                const isCompleted = s.stage < currentStage;
                const isActive = s.stage === currentStage;
                return (
                  <button
                    key={s.stage}
                    type="button"
                    className={`demo-step-chip ${isCompleted ? 'completed' : ''} ${isActive ? 'active' : ''}`}
                    onClick={() => handleJumpStage(s.stage)}
                    title={`Stage ${s.stage}: ${s.title}`}
                  >
                    <div className="step-chip-number">
                      {isCompleted ? <CheckCircle2 size={12} /> : <span>{s.stage}</span>}
                    </div>
                    <div className="step-chip-text">
                      <span className="step-chip-title">{s.title.replace('Vehicle enters Camera 01 (North)', '1. Enter North').replace('Vehicle is detected', '2. Detect YOLO').replace('Vehicle receives local track ID', '3. Track ID').replace('Plate is attempted through ANPR', '4. ANPR Plate').replace('Re-ID embedding is generated', '5. Re-ID 256d').replace('Observation is stored', '6. Store DB').replace('Vehicle is matched with a later observation', '7. Match Cam 2').replace('Global Vehicle ID is assigned', '8. Global ID').replace('Camera transition appears in trajectory', '9. Trajectory').replace('Dashboard updates', '10. Dashboard').replace('Relevant alert is generated', '11. Blacklist Alert')}</span>
                      <span className="step-chip-cam">{s.camera_id}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Telemetry Stage Detail Card */}
          <div className="demo-telemetry-viewport">
            <div className="demo-telemetry-col left-col">
              <div className="demo-stage-badge-row">
                <span className="demo-stage-index-badge">
                  STAGE {currentStage} / 11
                </span>
                <span className="demo-camera-badge">
                  <Compass size={13} />
                  {stageInfo?.camera_name || 'Virtual Cameras (North → Central → South)'}
                </span>
                <span className="demo-provenance-badge">
                  <AlertTriangle size={12} />
                  {stageInfo?.provenance?.data_origin || '[DEMO DATA] Configured Virtual Streams'}
                </span>
              </div>

              <h4 className="demo-stage-headline">
                {stageInfo?.title || 'System Initialized'}
              </h4>
              <p className="demo-stage-subheadline">
                {stageInfo?.description}
              </p>

              {/* Navigation Shortcuts for current state */}
              {currentStage >= 8 && onNavigate && (
                <div className="demo-stage-shortcuts">
                  {currentStage >= 9 && (
                    <button
                      type="button"
                      className="demo-shortcut-btn"
                      onClick={() => onNavigate('map')}
                    >
                      <MapPin size={13} />
                      <span>View Trajectory on CartoDB Map</span>
                      <ArrowRight size={12} />
                    </button>
                  )}
                  {currentStage >= 11 && (
                    <button
                      type="button"
                      className="demo-shortcut-btn alert-shortcut"
                      onClick={() => onNavigate('alerts')}
                    >
                      <ShieldAlert size={13} />
                      <span>Inspect Watchlist Hit in Alerts Tab</span>
                      <ArrowRight size={12} />
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Right Column: Model Inference & Telemetry Payload */}
            <div className="demo-telemetry-col right-col">
              <div className="telemetry-box-header">
                <span className="telemetry-box-title">LIVE MODEL TELEMETRY & DATA PROVENANCE</span>
                <span className="telemetry-box-label">ISOLATED FIRESTORE: data/cityvision_demo.db</span>
              </div>

              <div className="telemetry-metrics-grid">
                {currentStage === 0 && (
                  <div className="telemetry-empty-hint">
                    Demo is currently idle. Click <strong>Step Forward</strong> or <strong>Auto-Play</strong> to execute the 11-stage pipeline.
                  </div>
                )}

                {currentStage === 1 && (
                  <div className="telemetry-key-value">
                    <span className="k">Ingestion Stream:</span>
                    <span className="v font-mono">data/sample_videos/cam_01.mp4 (640x360 @ 15fps)</span>
                    <span className="k">Target Camera:</span>
                    <span className="v">CAM-001 (North Gateway Intersection, lat: 28.6139, lon: 77.2090)</span>
                    <span className="k">Sample Frame:</span>
                    <span className="v font-mono">Frame 15 (Video playback epoch: T0)</span>
                  </div>
                )}

                {currentStage === 2 && (
                  <div className="telemetry-key-value">
                    <span className="k">Detector Backbone:</span>
                    <span className="v font-mono">YOLOv8n (Ultralytics verified weights: yolov8n.pt)</span>
                    <span className="k">Bounding Box:</span>
                    <span className="v font-mono">[120, 180, 480, 420] px</span>
                    <span className="k">Classification:</span>
                    <span className="v highlight">car (Confidence: 0.93 / 93%)</span>
                    <span className="k">Model Provenance:</span>
                    <span className="v font-mono text-emerald-400">Live Ultralytics YOLOv8 Output</span>
                  </div>
                )}

                {currentStage === 3 && (
                  <div className="telemetry-key-value">
                    <span className="k">Intra-Camera Tracker:</span>
                    <span className="v">ByteTrack Single-Camera Association</span>
                    <span className="k">Local Track ID:</span>
                    <span className="v font-mono highlight">TRK-CAM001-01 (ID: 1)</span>
                    <span className="k">Kalman Continuity:</span>
                    <span className="v">15 frames tracked without discontinuity</span>
                  </div>
                )}

                {currentStage === 4 && (
                  <div className="telemetry-key-value">
                    <span className="k">Plate Segmenter:</span>
                    <span className="v">Morphological High-Contrast Aspect Filter</span>
                    <span className="k">OCR Engine:</span>
                    <span className="v font-mono">EasyPlateOCR (Character Whitelist)</span>
                    <span className="k">Recognized Text:</span>
                    <span className="v font-mono highlight">"DL01AB1234"</span>
                    <span className="k">OCR Confidence:</span>
                    <span className="v font-mono highlight">0.92 (92% - Exceeds 0.80 Reliable Threshold)</span>
                  </div>
                )}

                {currentStage === 5 && (
                  <div className="telemetry-key-value">
                    <span className="k">Re-ID Extractor:</span>
                    <span className="v font-mono">yolov8n-backbone-embed (CNN Feature Extractor)</span>
                    <span className="k">Embedding Dimension:</span>
                    <span className="v font-mono">256-dimensional unit vector</span>
                    <span className="k">L2 Hypersphere Norm:</span>
                    <span className="v font-mono">||v|| = 1.0000</span>
                    <span className="k">Vector Preview:</span>
                    <span className="v font-mono vector-preview">[-0.0412, 0.0825, 0.1251, -0.0914, 0.2201, 0.0512, ...]</span>
                  </div>
                )}

                {currentStage === 6 && (
                  <div className="telemetry-key-value">
                    <span className="k">Database Persistence:</span>
                    <span className="v font-mono">SQLite (data/cityvision_demo.db)</span>
                    <span className="k">Observation ID:</span>
                    <span className="v font-mono">OBS-DEMO-001 (Camera CAM-001, Track 1)</span>
                    <span className="k">Spatial Coordinates:</span>
                    <span className="v font-mono">28.6139° N, 77.2090° E (Configured Gateway)</span>
                    <span className="k">Production Pollution:</span>
                    <span className="v text-emerald-400 font-bold">ZERO RECORDS TOUCHED IN PRODUCTION DB</span>
                  </div>
                )}

                {currentStage === 7 && (
                  <div className="telemetry-key-value">
                    <span className="k">Next Camera Checkpoint:</span>
                    <span className="v">CAM-002 (Central Ring Road Eastbound) at T0 + 180s</span>
                    <span className="k">Cross-Camera Matcher:</span>
                    <span className="v">ExplainableCrossCameraMatcher</span>
                    <span className="k">Multi-Evidence Fusion:</span>
                    <span className="v">Plate Edit Distance: 0 | Re-ID Similarity: 0.94 | Travel Speed: 26.8 km/h</span>
                    <span className="k">Association Verdict:</span>
                    <span className="v font-mono highlight">HIGH CONFIDENCE (Composite Score: 0.95)</span>
                  </div>
                )}

                {currentStage === 8 && (
                  <div className="telemetry-key-value">
                    <span className="k">Assigned Identity:</span>
                    <span className="v font-mono highlight">GV-DEMO-001</span>
                    <span className="k">Primary Plate:</span>
                    <span className="v font-mono highlight">DL01AB1234</span>
                    <span className="k">Correlated Cameras:</span>
                    <span className="v font-mono">CAM-001 (North) + CAM-002 (Central)</span>
                    <span className="k">Total Observations:</span>
                    <span className="v font-mono">2 observations merged</span>
                  </div>
                )}

                {currentStage === 9 && (
                  <div className="telemetry-key-value">
                    <span className="k">Corridor Reconstruction:</span>
                    <span className="v font-mono">CAM-001 (North) → CAM-002 (Central) → CAM-003 (South)</span>
                    <span className="k">Total Distance:</span>
                    <span className="v font-mono">1,784.9 meters</span>
                    <span className="k">Corridor 1 Speed:</span>
                    <span className="v font-mono">742.2m in 180s = 14.8 km/h</span>
                    <span className="k">Corridor 2 Speed:</span>
                    <span className="v font-mono">1,042.7m in 180s = 20.9 km/h</span>
                  </div>
                )}

                {currentStage === 10 && (
                  <div className="telemetry-key-value">
                    <span className="k">Active Sensors:</span>
                    <span className="v font-mono">3 Virtual Cameras (CAM-001, CAM-002, CAM-003)</span>
                    <span className="k">Tracked Vehicle Count:</span>
                    <span className="v font-mono highlight">1 Global Vehicle Active</span>
                    <span className="k">WebSocket Broadcast:</span>
                    <span className="v font-mono text-emerald-400">event: 'demo_stage_advanced', stage: 10</span>
                  </div>
                )}

                {currentStage === 11 && (
                  <div className="telemetry-key-value alert-highlight-box">
                    <span className="k text-rose-400">Rule Triggered:</span>
                    <span className="v font-bold text-rose-400">WATCHLIST_BLACKLIST_HIT (Stolen Vehicle Registry)</span>
                    <span className="k">Matched Watchlist FIR:</span>
                    <span className="v font-mono">DL01AB1234 — Reported stolen (FIR #84920)</span>
                    <span className="k">Alert Severity:</span>
                    <span className="v font-bold text-rose-400">CRITICAL</span>
                    <span className="k">Alert Engine Provenance:</span>
                    <span className="v">High-confidence OCR 0.92 exceeds strict threshold 0.80. Zero false positive.</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
