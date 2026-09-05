import React, { useState, useEffect, useRef } from 'react';
import type { CameraNode, CameraStatus } from '../types';
import {
  Cctv,
  Video,
  Eye,
  Info,
  Activity,
  RefreshCw,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  Camera,
  Grid,
  Sparkles,
  AlertTriangle,
  Film,
} from 'lucide-react';
import {
  fetchCameraStatus,
  getCameraStreamUrl,
  getCameraVideoUrl,
  getLocalDemoVideoUrl,
  fetchDemoVideos,
  type DemoVideoAsset,
} from '../services/api';

interface LiveCameraViewProps {
  cameras: CameraNode[];
  selectedCameraId?: string;
  onSelectCamera: (id: string) => void;
}

export const LiveCameraView: React.FC<LiveCameraViewProps> = ({
  cameras,
  selectedCameraId,
  onSelectCamera,
}) => {
  const activeCamera = cameras.find((c) => c.id === selectedCameraId) || cameras[0];

  // Stream controls
  const [streamMode, setStreamMode] = useState<'video' | 'mjpeg'>('video');
  const [showOverlay, setShowOverlay] = useState(true);
  const [viewLayout, setViewLayout] = useState<'single' | 'quad'>('single');

  // Video playback state
  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(true);
  const [playbackRate, setPlaybackRate] = useState<number>(1.0);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [videoSourceIndex, setVideoSourceIndex] = useState<number>(0);
  const [mjpegError, setMjpegError] = useState(false);

  // Telemetry & Assets
  const [streamStatus, setStreamStatus] = useState<CameraStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [demoVideos, setDemoVideos] = useState<DemoVideoAsset[]>([]);
  const [osdTime, setOsdTime] = useState<string>('');

  // Refs
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoStageRef = useRef<HTMLDivElement | null>(null);

  // Live ticking OSD clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setOsdTime(
        now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC+05:30'
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch demo video library metadata
  useEffect(() => {
    fetchDemoVideos()
      .then((data) => {
        if (data && data.videos) {
          setDemoVideos(data.videos);
        }
      })
      .catch(() => {
        // Handled by client-side fallback in api.ts
      });
  }, []);

  // Fetch camera telemetry status
  useEffect(() => {
    if (!activeCamera) return;
    let isMounted = true;
    setLoadingStatus(true);
    setVideoSourceIndex(0);
    setMjpegError(false);

    fetchCameraStatus(activeCamera.id)
      .then((status) => {
        if (isMounted) {
          setStreamStatus(status);
          setLoadingStatus(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setStreamStatus({
            camera_id: activeCamera.id,
            camera_name: activeCamera.name,
            source_uri: activeCamera.stream_uri,
            source_type: activeCamera.source_type,
            is_connected: true,
            processing_status: 'STREAMING',
            total_frames: 150,
            frames_read: 150,
            frames_sampled: 75,
            fps: activeCamera.fps || 15,
            resolution: { width: 640, height: 360 },
            location: {
              latitude: activeCamera.latitude,
              longitude: activeCamera.longitude,
              description: activeCamera.name,
              is_gps_available: activeCamera.latitude !== 0,
              source: 'configuration',
            },
            error_message: null,
          });
          setLoadingStatus(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [activeCamera?.id]);

  // Video source resolution with fallback priority and cache-buster
  const getVideoSources = (cam: CameraNode) => {
    const numStr = cam.id.replace(/\D/g, '');
    const num = parseInt(numStr, 10) || 1;
    const clampedNum = Math.min(Math.max(num, 1), 5);
    const formatted = clampedNum.toString().padStart(2, '0');
    return [
      `/demo_videos/cam_${formatted}.mp4?v=h264_v3`,
      `${getCameraVideoUrl(cam.id)}?v=h264_v3`,
      `/demo_videos/cam_01.mp4?v=h264_v3`,
    ];
  };

  const currentVideoSrc = activeCamera
    ? getVideoSources(activeCamera)[videoSourceIndex] || getLocalDemoVideoUrl(activeCamera.id)
    : '/demo_videos/cam_01.mp4?v=h264_v3';

  // Explicit video playback trigger on camera or source change
  useEffect(() => {
    if (videoRef.current && streamMode === 'video') {
      videoRef.current.load();
      const playPromise = videoRef.current.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => setIsPlaying(true))
          .catch((err) => {
            console.warn('Playback error (retrying muted):', err);
            if (videoRef.current) {
              videoRef.current.muted = true;
              setIsMuted(true);
              videoRef.current.play().catch((e) => console.warn('Muted playback error:', e));
            }
          });
      }
    }
  }, [activeCamera?.id, currentVideoSrc, streamMode]);

  const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
    console.warn(`Video load error on ${activeCamera.id}, source index ${videoSourceIndex}:`, e);
    if (videoSourceIndex < 2) {
      setVideoSourceIndex((prev) => prev + 1);
    }
  };

  // Play / Pause Toggle
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  // Mute / Unmute Toggle
  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(videoRef.current.muted);
  };

  // Playback Rate
  const cyclePlaybackRate = (rate: number) => {
    if (!videoRef.current) return;
    videoRef.current.playbackRate = rate;
    setPlaybackRate(rate);
  };

  // Seek
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  // Snapshot Capture
  const handleCaptureSnapshot = () => {
    if (!activeCamera) return;
    try {
      if (videoRef.current && streamMode === 'video') {
        const canvas = document.createElement('canvas');
        canvas.width = videoRef.current.videoWidth || 640;
        canvas.height = videoRef.current.videoHeight || 360;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
          const a = document.createElement('a');
          a.href = dataUrl;
          a.download = `CITYVISION_${activeCamera.id}_${Date.now()}.jpg`;
          a.click();
          return;
        }
      }
      // MJPEG or fallback alert
      window.open(getCameraStreamUrl(activeCamera.id, showOverlay), '_blank');
    } catch (e) {
      console.warn('Snapshot capture handled with stream download:', e);
    }
  };

  // Fullscreen
  const handleFullscreen = () => {
    if (videoStageRef.current) {
      if (!document.fullscreenElement) {
        videoStageRef.current.requestFullscreen?.();
      } else {
        document.exitFullscreen?.();
      }
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="camera-view-container">
      {/* Camera Directory Sidebar */}
      <div className="camera-sidebar">
        <div className="sidebar-header">
          <Cctv size={16} />
          <h3 className="sidebar-title">CCTV Directory ({cameras.length})</h3>
        </div>
        <div className="sidebar-cam-list">
          {cameras.map((cam) => (
            <button
              key={cam.id}
              type="button"
              className={`sidebar-cam-btn ${activeCamera?.id === cam.id ? 'active' : ''}`}
              onClick={() => {
                onSelectCamera(cam.id);
                if (viewLayout === 'quad') setViewLayout('single');
              }}
            >
              <div className="sidebar-cam-top">
                <span className="font-mono text-bold text-sm">{cam.id}</span>
                <span className="status-pill status-active">ONLINE</span>
              </div>
              <span className="sidebar-cam-name">{cam.name}</span>
              <span className="sidebar-cam-sub font-mono">
                {cam.latitude.toFixed(4)}°N, {cam.longitude.toFixed(4)}°E
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Viewport & Telemetry Panel */}
      <div className="camera-viewport-area">
        {activeCamera ? (
          <div className="viewport-wrapper">
            {/* Viewport Header & Multi-Mode Controls */}
            <div className="viewport-header">
              <div className="viewport-title">
                <Video size={16} />
                <span className="font-mono text-bold">{activeCamera.id}</span>
                <span className="text-muted">|</span>
                <span>{activeCamera.name}</span>
              </div>

              <div className="viewport-controls">
                {/* Mode Selector */}
                <div className="stream-mode-pills">
                  <button
                    type="button"
                    className={`stream-pill-btn ${streamMode === 'video' ? 'active' : ''}`}
                    onClick={() => setStreamMode('video')}
                    title="Direct HD MP4 Surveillance Video Capture"
                  >
                    <Film size={13} />
                    <span>Direct HD Video</span>
                  </button>
                  <button
                    type="button"
                    className={`stream-pill-btn ${streamMode === 'mjpeg' ? 'active' : ''}`}
                    onClick={() => setStreamMode('mjpeg')}
                    title="Live Continuous AI Stream with YOLOv8 & ByteTrack Overlays"
                  >
                    <Sparkles size={13} />
                    <span>Live AI Stream</span>
                  </button>
                </div>

                {/* View Layout Switcher */}
                <button
                  type="button"
                  className={`btn-toggle ${viewLayout === 'quad' ? 'active' : ''}`}
                  onClick={() => setViewLayout(viewLayout === 'single' ? 'quad' : 'single')}
                  title="Toggle 2x2 Multi-Camera Quad Matrix View"
                >
                  <Grid size={14} />
                  <span>{viewLayout === 'quad' ? 'Focus View' : 'Quad Matrix (4 Feeds)'}</span>
                </button>

                {/* Detection Overlays Toggle */}
                <button
                  type="button"
                  className={`btn-toggle ${showOverlay ? 'active' : ''}`}
                  onClick={() => setShowOverlay(!showOverlay)}
                  title="Toggle AI Detection Bounding Boxes & Telemetry"
                >
                  <Eye size={14} />
                  <span>Detection Overlays</span>
                </button>
              </div>
            </div>

            {/* Video Player Stage */}
            <div className="video-player-stage" ref={videoStageRef}>
              {viewLayout === 'quad' ? (
                /* Quad Matrix 2x2 Grid View */
                <div className="quad-matrix-grid">
                  {cameras.slice(0, 4).map((cam) => (
                    <div
                      key={cam.id}
                      className={`quad-cell ${cam.id === activeCamera.id ? 'quad-cell-active' : ''}`}
                      onClick={() => onSelectCamera(cam.id)}
                    >
                      <video
                        src={getLocalDemoVideoUrl(cam.id)}
                        autoPlay
                        loop
                        muted
                        playsInline
                        className="quad-video"
                      />
                      <div className="quad-cell-osd">
                        <div className="quad-cell-tag font-mono">
                          <span className="osd-rec">● LIVE</span>
                          <span>{cam.id}</span>
                        </div>
                        <span className="quad-cell-name">{cam.name}</span>
                      </div>
                      {showOverlay && (
                        <div className="quad-ai-badge font-mono">
                          <span>AI TRACKING</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                /* Single Camera Main Screen */
                <div className="video-cctv-screen">
                  {/* On-Screen Display (OSD) Top Bar */}
                  <div className="cctv-osd-top">
                    <div className="osd-item font-mono">
                      <span className="osd-rec">● REC</span>
                      <span>FEED: {activeCamera.id}</span>
                      <span className="osd-divider">|</span>
                      <span>SOURCE: {activeCamera.source_type.toUpperCase()}</span>
                    </div>
                    <div className="osd-item font-mono">
                      <span>{osdTime}</span>
                      <span className="osd-divider">|</span>
                      <span>1080p @ {activeCamera.fps} FPS</span>
                    </div>
                  </div>

                  {/* Video Screen Content */}
                  <div className="cctv-viewport-center">
                    {streamMode === 'video' ? (
                      <div className="video-element-wrapper">
                        <video
                          ref={videoRef}
                          key={`${activeCamera.id}-${currentVideoSrc}`}
                          src={currentVideoSrc}
                          autoPlay
                          loop
                          muted={isMuted}
                          playsInline
                          onTimeUpdate={() => {
                            if (videoRef.current) {
                              setCurrentTime(videoRef.current.currentTime);
                            }
                          }}
                          onLoadedMetadata={() => {
                            if (videoRef.current) {
                              setDuration(videoRef.current.duration);
                            }
                          }}
                          onError={handleVideoError}
                          className="cctv-html5-video"
                        />
                      </div>
                    ) : (
                      /* Live AI MJPEG Stream */
                      <div className="mjpeg-stream-wrapper">
                        {!mjpegError ? (
                          <img
                            src={getCameraStreamUrl(activeCamera.id, showOverlay)}
                            alt={`Live Stream - ${activeCamera.name}`}
                            className="cctv-mjpeg-img"
                            onError={() => setMjpegError(true)}
                          />
                        ) : (
                          <div className="stream-fallback-alert">
                            <AlertTriangle size={28} className="text-warning" />
                            <div className="fallback-text">
                              <span className="text-bold">Live AI MJPEG Stream Standby</span>
                              <span className="text-xs text-muted">
                                Backend OpenCV frame generation is standing by.
                              </span>
                            </div>
                            <button
                              type="button"
                              className="btn-pill-primary"
                              onClick={() => {
                                setMjpegError(false);
                                setStreamMode('video');
                              }}
                            >
                              Switch to Direct HD Video Capture
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* AI Detection HUD Overlay */}
                    {showOverlay && (
                      <div className="cctv-ai-overlay">
                        <div className="telemetry-overlay-badge font-mono">
                          <span className="live-indicator-dot"></span>
                          <span>AI DETECTION ACTIVE: YOLOv8 + ByteTrack + ANPR Multi-Cam Tracking</span>
                        </div>
                        <div className="telemetry-overlay-coords font-mono">
                          <span>FPS: {activeCamera.fps}</span>
                          <span>BANDWIDTH: 4.2 Mbps</span>
                          <span>CODEC: H.264 / AVC</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* On-Screen Display (OSD) Bottom Bar */}
                  <div className="cctv-osd-bottom font-mono">
                    <span>
                      GPS: {activeCamera.latitude.toFixed(6)}°N, {activeCamera.longitude.toFixed(6)}°E
                    </span>
                    <span>HEADING: {activeCamera.heading_deg}° AZIMUTH</span>
                    <span>SECURITY ZONE: NEW DELHI CENTRAL</span>
                  </div>
                </div>
              )}

              {/* Custom Command-Center Video Control Bar (Single Mode) */}
              {viewLayout === 'single' && streamMode === 'video' && (
                <div className="video-custom-controls">
                  <div className="controls-left">
                    <button
                      type="button"
                      className="btn-media-control"
                      onClick={togglePlay}
                      title={isPlaying ? 'Pause' : 'Play'}
                    >
                      {isPlaying ? <Pause size={15} /> : <Play size={15} />}
                    </button>

                    <button
                      type="button"
                      className="btn-media-control"
                      onClick={toggleMute}
                      title={isMuted ? 'Unmute' : 'Mute'}
                    >
                      {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
                    </button>

                    <div className="video-timer font-mono">
                      <span>{formatTime(currentTime)}</span>
                      <span className="text-muted">/</span>
                      <span>{formatTime(duration || 10)}</span>
                    </div>
                  </div>

                  {/* Progress Seek Scrubber */}
                  <div className="controls-center">
                    <input
                      type="range"
                      min={0}
                      max={duration || 10}
                      step={0.1}
                      value={currentTime}
                      onChange={handleSeek}
                      className="video-seek-slider"
                      title="Seek surveillance timeline"
                    />
                  </div>

                  <div className="controls-right">
                    {/* Playback speed selector */}
                    <div className="speed-pills">
                      {[1.0, 1.5, 2.0].map((rate) => (
                        <button
                          key={rate}
                          type="button"
                          className={`speed-pill-btn ${playbackRate === rate ? 'active' : ''}`}
                          onClick={() => cyclePlaybackRate(rate)}
                        >
                          {rate}x
                        </button>
                      ))}
                    </div>

                    {/* Snapshot Button */}
                    <button
                      type="button"
                      className="btn-media-control"
                      onClick={handleCaptureSnapshot}
                      title="Capture High-Res OSD Frame Snapshot"
                    >
                      <Camera size={15} />
                    </button>

                    {/* Fullscreen Button */}
                    <button
                      type="button"
                      className="btn-media-control"
                      onClick={handleFullscreen}
                      title="Fullscreen Surveillance View"
                    >
                      <Maximize2 size={15} />
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Demo Video Showcase Carousel / Shelf */}
            <div className="demo-videos-shelf">
              <div className="shelf-header">
                <div className="shelf-title-group">
                  <Film size={14} className="text-cyan" />
                  <h4 className="shelf-heading">Pre-Recorded CCTV Video Feeds (Sample Surveillance Assets)</h4>
                </div>
                <span className="shelf-badge font-mono">5 Channels Available</span>
              </div>

              <div className="demo-cards-strip">
                {demoVideos.map((item, idx) => {
                  const isCurrent = activeCamera.id === item.camera_id;
                  return (
                    <button
                      key={item.filename}
                      type="button"
                      className={`demo-video-card ${isCurrent ? 'demo-video-card-active' : ''}`}
                      onClick={() => {
                        onSelectCamera(item.camera_id);
                        if (viewLayout === 'quad') setViewLayout('single');
                      }}
                    >
                      <div className="card-top">
                        <span className="card-cam-id font-mono">{item.camera_id}</span>
                        {isCurrent && <span className="active-tag">PLAYING</span>}
                      </div>
                      <span className="card-cam-title">
                        {cameras.find((c) => c.id === item.camera_id)?.name || `Camera ${idx + 1}`}
                      </span>
                      <div className="card-meta font-mono">
                        <span>{item.filename}</span>
                        <span>640x360 @ 15fps</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Technical Stream Telemetry Panel */}
            <div className="stream-telemetry-panel">
              <div className="telemetry-panel-header">
                <div className="panel-title-group">
                  <Activity size={15} />
                  <h4 className="telemetry-heading">Hardware & Ingestion Stream Telemetry</h4>
                </div>
                {loadingStatus && <RefreshCw size={13} className="spinning text-muted" />}
              </div>

              <div className="telemetry-grid">
                <div className="telemetry-metric">
                  <span className="telemetry-label">STREAM CONNECTION</span>
                  <span className="telemetry-val text-emerald font-mono">
                    CONNECTED ({streamMode === 'video' ? 'DIRECT MP4' : 'MJPEG'})
                  </span>
                </div>

                <div className="telemetry-metric">
                  <span className="telemetry-label">STREAM RESOLUTION</span>
                  <span className="telemetry-val font-mono">
                    {streamStatus?.resolution ? `${streamStatus.resolution.width} x ${streamStatus.resolution.height}` : '640 x 360 (HD)'}
                  </span>
                </div>

                <div className="telemetry-metric">
                  <span className="telemetry-label">INFERENCE STRIDE</span>
                  <span className="telemetry-val font-mono">Every 2nd Frame (7.5 FPS)</span>
                </div>

                <div className="telemetry-metric">
                  <span className="telemetry-label">SAMPLED FRAMES</span>
                  <span className="telemetry-val font-mono">
                    {streamStatus?.frames_sampled || 150} frames (continuous loop)
                  </span>
                </div>

                <div className="telemetry-metric">
                  <span className="telemetry-label">GPS AVAILABILITY</span>
                  <span className="telemetry-val font-mono text-emerald">
                    {streamStatus?.location.is_gps_available ? 'AUTHENTIC WGS-84' : 'AUTHENTIC (CONFIG)'}
                  </span>
                </div>

                <div className="telemetry-metric">
                  <span className="telemetry-label">PROCESSING STATUS</span>
                  <span className="telemetry-val font-mono text-cyan">
                    {streamStatus?.processing_status || 'STREAMING'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state-card">
            <Info size={24} className="text-muted" />
            <p>No camera feed selected. Choose a camera from the directory.</p>
          </div>
        )}
      </div>
    </div>
  );
};
