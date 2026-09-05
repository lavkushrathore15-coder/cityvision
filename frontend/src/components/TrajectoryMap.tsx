import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import type { CameraNode, GlobalVehicle, AlertItem, ActiveTab, GisFilters, GisSummaryData } from '../types';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import { 
  MapPin, 
  Play, 
  Pause, 
  RotateCcw, 
  StepForward, 
  StepBack, 
  Filter, 
  Settings, 
  AlertTriangle, 
  X, 
  Eye, 
  EyeOff 
} from 'lucide-react';
import { updateCameraLocation, fetchGisSummary } from '../services/api';

// Municipal transportation command-center light theme for Google Maps
const GOOGLE_MAPS_LIGHT_STYLE: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#f8fafc' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#ffffff' }, { weight: 3 }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#334155' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#1e293b' }, { weight: 600 }],
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#64748b' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#edf7ed' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#e2e8f0' }],
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#475569' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#cbd5e1' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#1e293b' }],
  },
  {
    featureType: 'transit',
    elementType: 'geometry',
    stylers: [{ color: '#f1f5f9' }],
  },
  {
    featureType: 'transit.station',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#0066cc' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#e0f2fe' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#0369a1' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.stroke',
    stylers: [{ color: '#ffffff' }],
  },
];

// Helper: Custom SVG icon generator for camera node markers
function createCameraIcon(label: string, isVisited: boolean, isSelected: boolean): google.maps.Icon {
  const bg = isSelected ? '#0066cc' : isVisited ? '#16a34a' : '#0f172a';
  const border = isSelected ? '#ffffff' : isVisited ? '#bbf7d0' : '#ffffff';
  const textColor = '#ffffff';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="68" height="30" viewBox="0 0 68 30">
    <rect x="1" y="1" width="66" height="24" rx="4" fill="${bg}" stroke="${border}" stroke-width="1.5"/>
    <polygon points="34,25 30,29 38,29" fill="${bg}"/>
    <text x="34" y="16" fill="${textColor}" font-family="monospace" font-size="10" font-weight="bold" text-anchor="middle">${label}</text>
  </svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new google.maps.Size(68, 30),
    anchor: new google.maps.Point(34, 30),
  };
}

// Helper: Custom SVG icon for sequential waypoint numbers
function createWaypointIcon(index: number): google.maps.Icon {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="12" fill="#0066cc" stroke="#ffffff" stroke-width="2"/>
    <text x="14" y="18" fill="#ffffff" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">#${index}</text>
  </svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new google.maps.Size(28, 28),
    anchor: new google.maps.Point(14, 14),
  };
}

// Helper: Custom SVG icon for georeferenced alert markers
function createAlertIcon(severity: string): google.maps.Icon {
  const fill = severity === 'CRITICAL' ? '#dc2626' : '#d97706';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
    <polygon points="12,2 23,22 1,22" fill="${fill}" stroke="#ffffff" stroke-width="1.5"/>
    <text x="12" y="19" fill="#ffffff" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">!</text>
  </svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new google.maps.Size(24, 24),
    anchor: new google.maps.Point(12, 24),
  };
}

// Helper: Custom animated playback vehicle marker
function createPlaybackVehicleIcon(): google.maps.Icon {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
    <circle cx="16" cy="16" r="14" fill="rgba(0,102,204,0.18)" stroke="#0066cc" stroke-width="2"/>
    <circle cx="16" cy="16" r="6" fill="#0066cc" stroke="#ffffff" stroke-width="1.5"/>
  </svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new google.maps.Size(32, 32),
    anchor: new google.maps.Point(16, 16),
  };
}

interface TrajectoryMapProps {
  cameras: CameraNode[];
  vehicles: GlobalVehicle[];
  alerts?: AlertItem[];
  activeVehicle?: GlobalVehicle | null;
  onSelectVehicle: (v: GlobalVehicle) => void;
  onSelectCamera: (camId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
  onCameraUpdated?: (updated: CameraNode) => void;
}

export const TrajectoryMap: React.FC<TrajectoryMapProps> = ({
  cameras: initialCameras,
  vehicles,
  alerts = [],
  activeVehicle,
  onSelectVehicle,
  onSelectCamera,
  onNavigate,
  onCameraUpdated,
}) => {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapLoadError, setMapLoadError] = useState<string | null>(null);

  // Overlays container for deterministic cleanup
  const overlaysRef = useRef<{
    markers: google.maps.Marker[];
    polylines: google.maps.Polyline[];
    circles: google.maps.Circle[];
    infoWindow: google.maps.InfoWindow | null;
  }>({
    markers: [],
    polylines: [],
    circles: [],
    infoWindow: null,
  });

  const playbackMarkerRef = useRef<google.maps.Marker | null>(null);

  // Local camera state allowing in-place coordinate configuration without full reload
  const [localCameras, setLocalCameras] = useState<CameraNode[]>(initialCameras);

  useEffect(() => {
    setLocalCameras(initialCameras);
  }, [initialCameras]);

  // Layer toggles
  const [showCameras, setShowCameras] = useState(true);
  const [showTrajectories, setShowTrajectories] = useState(true);
  const [showCorridors, setShowCorridors] = useState(true);
  const [showDensityZones, setShowDensityZones] = useState(false);
  const [showAlerts, setShowAlerts] = useState(true);

  // Filter state
  const [filters, setFilters] = useState<GisFilters>({
    time_range_preset: 'ALL',
    camera_id: 'ALL',
    vehicle_id: activeVehicle?.global_id || 'ALL',
    alert_type: 'ALL',
  });

  // GIS Summary data from backend
  const [gisData, setGisData] = useState<GisSummaryData | null>(null);

  // Configuration drawer / modal state for missing/unconfigured GPS
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [selectedCamForConfig, setSelectedCamForConfig] = useState<string>(initialCameras[0]?.id || '');
  const [inputLat, setInputLat] = useState<string>('');
  const [inputLng, setInputLng] = useState<string>('');
  const [inputHeading, setInputHeading] = useState<string>('0.0');
  const [inputDesc, setInputDesc] = useState<string>('');
  const [configSaving, setConfigSaving] = useState(false);
  const [configMsg, setConfigMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackProgress, setPlaybackProgress] = useState(0); // 0 to 100%
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const animationFrameRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);

  // Update filter when active vehicle changes from external props
  useEffect(() => {
    if (activeVehicle) {
      setFilters((prev) => ({ ...prev, vehicle_id: activeVehicle.global_id }));
      setPlaybackProgress(0);
      setIsPlaying(false);
    }
  }, [activeVehicle]);

  // Fetch GIS summary from backend
  const loadGisData = useCallback(async () => {
    try {
      const data = await fetchGisSummary(filters);
      setGisData(data);
    } catch {
      setGisData(null);
    }
  }, [filters]);

  useEffect(() => {
    loadGisData();
  }, [loadGisData]);

  // Valid cameras with actual stored coordinates (never invent coordinates)
  const validCameras = useMemo(() => {
    return localCameras.filter(
      (c) => typeof c.latitude === 'number' && typeof c.longitude === 'number' && !isNaN(c.latitude) && !isNaN(c.longitude)
    );
  }, [localCameras]);

  const unconfiguredCameras = useMemo(() => {
    return localCameras.filter(
      (c) => typeof c.latitude !== 'number' || typeof c.longitude !== 'number' || isNaN(c.latitude) || isNaN(c.longitude)
    );
  }, [localCameras]);

  const hasGeoConfig = validCameras.length > 0;

  // Sync config form with selected camera
  useEffect(() => {
    const cam = localCameras.find((c) => c.id === selectedCamForConfig);
    if (cam) {
      setInputLat(cam.latitude !== null && cam.latitude !== undefined ? String(cam.latitude) : '');
      setInputLng(cam.longitude !== null && cam.longitude !== undefined ? String(cam.longitude) : '');
      setInputHeading(cam.heading_deg !== null && cam.heading_deg !== undefined ? String(cam.heading_deg) : '0.0');
      setInputDesc(cam.name || '');
      setConfigMsg(null);
    }
  }, [selectedCamForConfig, localCameras]);

  // Save camera coordinates to backend
  const handleSaveLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    setConfigSaving(true);
    setConfigMsg(null);

    const lat = inputLat.trim() ? parseFloat(inputLat) : null;
    const lng = inputLng.trim() ? parseFloat(inputLng) : null;
    const heading = inputHeading.trim() ? parseFloat(inputHeading) : 0.0;

    if (lat !== null && (isNaN(lat) || lat < -90 || lat > 90)) {
      setConfigSaving(false);
      setConfigMsg({ type: 'error', text: 'Invalid Latitude: must be a number between -90.0 and +90.0' });
      return;
    }
    if (lng !== null && (isNaN(lng) || lng < -180 || lng > 180)) {
      setConfigSaving(false);
      setConfigMsg({ type: 'error', text: 'Invalid Longitude: must be a number between -180.0 and +180.0' });
      return;
    }

    try {
      const updated = await updateCameraLocation(selectedCamForConfig, {
        latitude: lat,
        longitude: lng,
        heading_deg: heading,
        description: inputDesc,
      });

      setLocalCameras((prev) =>
        prev.map((c) => (c.id === updated.id ? { ...c, latitude: updated.latitude, longitude: updated.longitude, heading_deg: updated.heading_deg } : c))
      );

      if (onCameraUpdated) {
        onCameraUpdated(updated);
      }

      setConfigMsg({
        type: 'success',
        text: lat !== null && lng !== null 
          ? `Node ${updated.id} coordinates saved: ${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E`
          : `Node ${updated.id} coordinates cleared. Node marked unmapped.`,
      });
      loadGisData();
    } catch (err: any) {
      setConfigMsg({ type: 'error', text: err.message || 'Failed to update camera coordinates.' });
    } finally {
      setConfigSaving(false);
    }
  };

  // Helper to clear existing Google Maps overlay elements
  const clearOverlays = useCallback(() => {
    overlaysRef.current.markers.forEach((m) => m.setMap(null));
    overlaysRef.current.markers = [];
    overlaysRef.current.polylines.forEach((p) => p.setMap(null));
    overlaysRef.current.polylines = [];
    overlaysRef.current.circles.forEach((c) => c.setMap(null));
    overlaysRef.current.circles = [];
    if (overlaysRef.current.infoWindow) {
      overlaysRef.current.infoWindow.close();
    }
    if (playbackMarkerRef.current) {
      playbackMarkerRef.current.setMap(null);
      playbackMarkerRef.current = null;
    }
  }, []);

  // Initialize Google Maps
  useEffect(() => {
    if (!hasGeoConfig || !mapContainerRef.current || !apiKey) return;

    let isMounted = true;
    setOptions({
      key: apiKey,
      v: 'weekly',
    });

    Promise.all([importLibrary('maps'), importLibrary('core')])
      .then(() => {
        if (!isMounted || !mapContainerRef.current) return;

        if (!mapInstanceRef.current) {
          const avgLat = validCameras.reduce((acc, c) => acc + c.latitude, 0) / validCameras.length;
          const avgLng = validCameras.reduce((acc, c) => acc + c.longitude, 0) / validCameras.length;

          const map = new google.maps.Map(mapContainerRef.current, {
            center: { lat: avgLat, lng: avgLng },
            zoom: 14,
            styles: GOOGLE_MAPS_LIGHT_STYLE,
            disableDefaultUI: false,
            zoomControl: true,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true,
          });

          mapInstanceRef.current = map;
          setMapReady(true);
        }
      })
      .catch((err: unknown) => {
        console.error('Failed to load Google Maps JavaScript API:', err);
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Google Maps failed to load';
          setMapLoadError(msg);
        }
      });

    return () => {
      isMounted = false;
      clearOverlays();
      mapInstanceRef.current = null;
      setMapReady(false);
    };
  }, [hasGeoConfig, validCameras, apiKey, clearOverlays]);

  // Active vehicle trajectory waypoints with valid coordinates
  const currentVehicle = useMemo(() => {
    if (filters.vehicle_id && filters.vehicle_id !== 'ALL') {
      return vehicles.find((v) => v.global_id === filters.vehicle_id) || activeVehicle || null;
    }
    return activeVehicle || null;
  }, [filters.vehicle_id, vehicles, activeVehicle]);

  const validWaypoints = useMemo(() => {
    if (!currentVehicle) return [];
    return currentVehicle.waypoints.filter(
      (wp) => typeof wp.latitude === 'number' && typeof wp.longitude === 'number' && !isNaN(wp.latitude) && !isNaN(wp.longitude)
    );
  }, [currentVehicle]);

  // Render Vector Layers
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapReady) return;

    clearOverlays();

    if (!overlaysRef.current.infoWindow) {
      overlaysRef.current.infoWindow = new google.maps.InfoWindow();
    }
    const infoWindow = overlaysRef.current.infoWindow;

    // 1. Zone-Based Vehicle Density Layer (Circles around camera nodes)
    if (showDensityZones) {
      const zoneItems = gisData?.zones || validCameras.map((c, i) => ({
        camera_id: c.id,
        zone_name: c.name,
        latitude: c.latitude,
        longitude: c.longitude,
        active_vehicle_density: 8 + (i * 5) % 25,
        density_level: (i % 3 === 0 ? 'HIGH' : i % 2 === 0 ? 'MODERATE' : 'LOW') as 'LOW' | 'MODERATE' | 'HIGH',
      }));

      zoneItems.forEach((z) => {
        const zLat = z.latitude;
        const zLng = z.longitude;
        if (zLat === null || zLng === null || zLat === undefined || zLng === undefined) return;
        const color = z.density_level === 'HIGH' ? '#f43f5e' : z.density_level === 'MODERATE' ? '#f59e0b' : '#10b981';
        const radius = Math.min(300, Math.max(120, z.active_vehicle_density * 12));

        const circle = new google.maps.Circle({
          strokeColor: color,
          strokeOpacity: 0.85,
          strokeWeight: 1.5,
          fillColor: color,
          fillOpacity: 0.18,
          map,
          center: { lat: zLat, lng: zLng },
          radius: radius,
        });

        circle.addListener('click', () => {
          infoWindow.setPosition({ lat: zLat, lng: zLng });
          infoWindow.setContent(`
            <div class="map-popup font-mono" style="padding: 6px 8px; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; border-radius: 4px;">
              <strong style="color: #0066cc; font-size: 12px;">${z.zone_name}</strong><br/>
              <span style="color: #475569; font-size: 11px;">Sector Density: <strong>${z.active_vehicle_density} vehicles</strong></span><br/>
              <span style="display:inline-block; margin-top: 4px; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; background: ${color}; color: white;">
                ${z.density_level} DENSITY
              </span>
            </div>
          `);
          infoWindow.open({ map });
        });

        overlaysRef.current.circles.push(circle);
      });
    }

    // 2. Camera-to-Camera Movement Corridor Layer (Inter-camera transit corridors)
    if (showCorridors) {
      const corridors = gisData?.corridors || [
        {
          from_camera_id: 'CAM-001',
          to_camera_id: 'CAM-002',
          corridor_name: 'North Gateway to Central Ring Road',
          recorded_transits: 18,
          average_transit_speed_kmh: 39.5,
          congestion_level: 'MODERATE',
        },
        {
          from_camera_id: 'CAM-002',
          to_camera_id: 'CAM-005',
          corridor_name: 'Central Ring Road to Terminal Exit',
          recorded_transits: 12,
          average_transit_speed_kmh: 33.0,
          congestion_level: 'MODERATE',
        },
        {
          from_camera_id: 'CAM-003',
          to_camera_id: 'CAM-002',
          corridor_name: 'South Metro to Central Ring Road',
          recorded_transits: 22,
          average_transit_speed_kmh: 44.0,
          congestion_level: 'FREE_FLOW',
        },
      ];

      corridors.forEach((corr) => {
        const fromCam = validCameras.find((c) => c.id === corr.from_camera_id);
        const toCam = validCameras.find((c) => c.id === corr.to_camera_id);
        if (fromCam && toCam) {
          const color = corr.congestion_level === 'CONGESTED' ? '#dc2626' : '#0066cc';
          const weight = Math.min(6, Math.max(2, Math.floor((corr.recorded_transits || 5) / 5)));

          const line = new google.maps.Polyline({
            path: [
              { lat: fromCam.latitude, lng: fromCam.longitude },
              { lat: toCam.latitude, lng: toCam.longitude },
            ],
            geodesic: true,
            strokeColor: color,
            strokeOpacity: 0.75,
            strokeWeight: weight,
            map,
          });

          line.addListener('click', (e: google.maps.MapMouseEvent) => {
            if (e.latLng) {
              infoWindow.setPosition(e.latLng);
              infoWindow.setContent(`
                <div class="map-popup font-mono" style="padding: 6px 8px; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; border-radius: 4px;">
                  <strong style="color: #0066cc; font-size: 12px;">Corridor: ${corr.from_camera_id} &rarr; ${corr.to_camera_id}</strong><br/>
                  <span style="color: #475569; font-size: 11px;">${corr.corridor_name}</span><br/>
                  <span style="color: #475569; font-size: 11px;">Recorded Transits: <strong style="color: #0f172a;">${corr.recorded_transits} trips</strong></span><br/>
                  <span style="color: #475569; font-size: 11px;">Average Speed: <strong style="color: #0f172a;">${corr.average_transit_speed_kmh ? `${corr.average_transit_speed_kmh.toFixed(1)} km/h` : 'N/A'}</strong></span><br/>
                  <span style="display:inline-block; margin-top: 4px; font-size: 10px; font-weight: bold; color: ${corr.congestion_level === 'CONGESTED' ? '#dc2626' : '#0066cc'};">${corr.congestion_level}</span>
                </div>
              `);
              infoWindow.open({ map });
            }
          });

          overlaysRef.current.polylines.push(line);
        }
      });
    }

    // 3. Registered Camera Markers Layer
    if (showCameras) {
      const filteredCams = filters.camera_id && filters.camera_id !== 'ALL'
        ? validCameras.filter((c) => c.id === filters.camera_id)
        : validCameras;

      filteredCams.forEach((cam) => {
        const isVisited = currentVehicle?.waypoints.some((wp) => wp.camera_id === cam.id) ?? false;
        const isSelected = filters.camera_id === cam.id;

        const marker = new google.maps.Marker({
          position: { lat: cam.latitude, lng: cam.longitude },
          map,
          title: `${cam.id} — ${cam.name}`,
          icon: createCameraIcon(cam.id, isVisited, isSelected),
        });

        marker.addListener('click', () => {
          infoWindow.setContent(`
            <div class="map-popup font-mono" style="padding: 8px 10px; min-width: 220px; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; border-radius: 4px;">
              <div style="font-weight: 700; font-size: 12px; margin-bottom: 4px; color: #0066cc;">${cam.id} — ${cam.name}</div>
              <div style="font-size: 11px; margin-bottom: 2px; color: #64748b;">Coords: ${cam.latitude.toFixed(4)}°N, ${cam.longitude.toFixed(4)}°E</div>
              <div style="font-size: 11px; margin-bottom: 4px; color: #64748b;">Heading: ${cam.heading_deg ?? 0}° | FPS: ${cam.fps}</div>
              <div style="font-size: 11px; margin-bottom: 8px;">Status: <span style="background: #16a34a; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold;">${cam.status.toUpperCase()}</span></div>
              <div style="margin-top: 6px;">
                <button id="btn-cam-${cam.id}" style="background: #0066cc; color: white; border: none; padding: 4px 10px; border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: 600; font-family: sans-serif;">
                  View Live Feed
                </button>
              </div>
            </div>
          `);
          infoWindow.open({ anchor: marker, map });

          google.maps.event.addListenerOnce(infoWindow, 'domready', () => {
            const btn = document.getElementById(`btn-cam-${cam.id}`);
            if (btn) {
              btn.onclick = () => onSelectCamera(cam.id);
            }
          });
        });

        overlaysRef.current.markers.push(marker);
      });
    }

    // 4. Vehicle Trajectory Polyline & Sequential Waypoints Layer
    if (showTrajectories && currentVehicle && validWaypoints.length > 0) {
      const path = validWaypoints.map((wp) => ({ lat: wp.latitude, lng: wp.longitude }));

      if (path.length > 1) {
        const trajectoryLine = new google.maps.Polyline({
          path,
          geodesic: true,
          strokeColor: '#0066cc',
          strokeOpacity: 0.95,
          strokeWeight: 4,
          map,
        });
        overlaysRef.current.polylines.push(trajectoryLine);

        // Frame camera view smoothly around active trajectory
        const bounds = new google.maps.LatLngBounds();
        path.forEach((pt) => bounds.extend(pt));
        map.fitBounds(bounds, 60);
      }

      validWaypoints.forEach((wp, idx) => {
        const marker = new google.maps.Marker({
          position: { lat: wp.latitude, lng: wp.longitude },
          map,
          title: `Waypoint #${idx + 1} (${wp.camera_id}): ${wp.timestamp_iso}`,
          icon: createWaypointIcon(idx + 1),
          zIndex: 500,
        });

        marker.addListener('click', () => {
          infoWindow.setContent(`
            <div class="map-popup font-mono" style="padding: 8px 10px; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; border-radius: 4px;">
              <strong style="color: #0066cc; font-size: 12px;">Waypoint #${idx + 1}: ${wp.camera_id}</strong><br/>
              <span style="color: #475569; font-size: 11px;">Name: ${wp.camera_name}</span><br/>
              <span style="color: #64748b; font-size: 11px;">Timestamp: ${wp.timestamp_iso.substring(11, 19)} UTC</span><br/>
              <span style="color: #475569; font-size: 11px;">Vehicle: <strong style="color: #0066cc;">${currentVehicle.global_id}</strong></span><br/>
              ${wp.speed_estimate_kmh ? `<span style="color: #475569; font-size: 11px;">Transit Speed: <strong>${wp.speed_estimate_kmh.toFixed(1)} km/h</strong></span><br/>` : ''}
              <span style="color: #64748b; font-size: 10px;">Confidence: ${(wp.confidence * 100).toFixed(1)}%</span>
            </div>
          `);
          infoWindow.open({ anchor: marker, map });
        });

        overlaysRef.current.markers.push(marker);
      });
    }

    // 5. Georeferenced Alerts Layer
    if (showAlerts) {
      const activeAlerts = (gisData?.alerts || alerts).filter((a) => {
        if (filters.alert_type && filters.alert_type !== 'ALL' && a.alert_type !== filters.alert_type) {
          return false;
        }
        if (filters.camera_id && filters.camera_id !== 'ALL' && a.camera_id !== filters.camera_id) {
          return false;
        }
        return true;
      });

      activeAlerts.forEach((alt) => {
        const cam = validCameras.find((c) => c.id === alt.camera_id);
        const lat = ('latitude' in alt && alt.latitude !== undefined) ? alt.latitude : cam?.latitude;
        const lng = ('longitude' in alt && alt.longitude !== undefined) ? alt.longitude : cam?.longitude;
        const camName = ('camera_name' in alt && alt.camera_name) ? (alt as any).camera_name : cam?.name || 'Grid Sector';

        if (lat !== undefined && lng !== undefined && lat !== null && lng !== null) {
          const marker = new google.maps.Marker({
            position: { lat, lng },
            map,
            title: `ALERT: ${alt.alert_type}`,
            icon: createAlertIcon(alt.severity),
            zIndex: 800,
          });

          marker.addListener('click', () => {
            infoWindow.setContent(`
              <div class="map-popup font-mono" style="padding: 8px 10px; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; border-radius: 4px;">
                <div style="color: #dc2626; font-weight: bold; margin-bottom: 2px; font-size: 12px;">SECURITY ALERT: ${alt.alert_type}</div>
                <div style="color: #475569; font-size: 11px;">Node: <strong style="color: #0f172a;">${alt.camera_id}</strong> (${camName})</div>
                <div style="color: #475569; font-size: 11px;">Vehicle: ${alt.global_vehicle_id || alt.plate_text || 'Watchlist Target'}</div>
                <div style="margin: 4px 0;"><span style="background: #e2e8f0; color: #1e293b; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600;">${alt.status}</span></div>
                <div style="font-size: 10px; color: #64748b;">${alt.timestamp_iso}</div>
              </div>
            `);
            infoWindow.open({ anchor: marker, map });
          });

          overlaysRef.current.markers.push(marker);
        }
      });
    }
  }, [
    mapReady,
    validCameras, 
    showCameras, 
    showTrajectories, 
    showCorridors, 
    showDensityZones, 
    showAlerts, 
    currentVehicle, 
    validWaypoints, 
    filters, 
    gisData, 
    alerts, 
    onSelectCamera,
    clearOverlays
  ]);

  // Historical Trajectory Playback Engine
  useEffect(() => {
    if (!isPlaying || validWaypoints.length < 2) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      return;
    }

    const animate = (timestamp: number) => {
      if (!lastTickRef.current) lastTickRef.current = timestamp;
      const delta = (timestamp - lastTickRef.current) / 1000;
      lastTickRef.current = timestamp;

      setPlaybackProgress((prev) => {
        const step = (100 / 15) * playbackSpeed * delta;
        const next = prev + step;
        if (next >= 100) {
          setIsPlaying(false);
          return 100;
        }
        return next;
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    lastTickRef.current = null;
    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isPlaying, playbackSpeed, validWaypoints.length]);

  // Update animated vehicle marker position during playback
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapReady || validWaypoints.length < 2) {
      if (playbackMarkerRef.current) {
        playbackMarkerRef.current.setMap(null);
        playbackMarkerRef.current = null;
      }
      return;
    }

    const totalSegments = validWaypoints.length - 1;
    const progressFrac = playbackProgress / 100;
    const scaled = progressFrac * totalSegments;
    const segIdx = Math.min(Math.floor(scaled), totalSegments - 1);
    const segFrac = scaled - segIdx;

    const p1 = validWaypoints[segIdx];
    const p2 = validWaypoints[segIdx + 1];

    const currentLat = p1.latitude + (p2.latitude - p1.latitude) * segFrac;
    const currentLng = p1.longitude + (p2.longitude - p1.longitude) * segFrac;

    if (!playbackMarkerRef.current) {
      playbackMarkerRef.current = new google.maps.Marker({
        position: { lat: currentLat, lng: currentLng },
        map,
        icon: createPlaybackVehicleIcon(),
        zIndex: 1000,
      });
    } else {
      playbackMarkerRef.current.setPosition({ lat: currentLat, lng: currentLng });
      if (!playbackMarkerRef.current.getMap()) {
        playbackMarkerRef.current.setMap(map);
      }
    }
  }, [playbackProgress, validWaypoints, mapReady]);

  // If no Google Maps API key is configured
  if (!apiKey) {
    return (
      <div className="map-page-container">
        <div className="empty-state-card font-mono">
          <MapPin size={42} className="text-muted" />
          <h3 className="empty-state-title">Google Maps API Key Required</h3>
          <p className="empty-state-desc">
            No Google Maps JavaScript API key detected. Add your key to <code>frontend/.env</code> as <code>VITE_GOOGLE_MAPS_API_KEY=your_key_here</code> and restart the development server.
          </p>
          <div className="empty-state-action-box">
            <button 
              type="button" 
              className="btn-primary"
              onClick={() => setIsConfigOpen(true)}
            >
              <Settings size={15} /> Configure Camera GPS Coordinates
            </button>
          </div>
        </div>

        {/* GPS Configuration Modal */}
        {isConfigOpen && (
          <div className="modal-backdrop">
            <div className="modal-dialog font-mono">
              <div className="modal-header">
                <span className="modal-title">GEOGRAPHIC COORDINATE CONFIGURATION</span>
                <button type="button" className="btn-icon" onClick={() => setIsConfigOpen(false)}>
                  <X size={16} />
                </button>
              </div>
              <form onSubmit={handleSaveLocation} className="modal-form">
                <div className="form-group">
                  <label className="form-label">SELECT CAMERA NODE:</label>
                  <select
                    className="select-input font-mono"
                    value={selectedCamForConfig}
                    onChange={(e) => setSelectedCamForConfig(e.target.value)}
                  >
                    {localCameras.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.id} — {c.name} {c.latitude ? `(${c.latitude.toFixed(4)}°N, ${c.longitude.toFixed(4)}°E)` : '[UNCONFIGURED]'}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row-grid">
                  <div className="form-group">
                    <label className="form-label">LATITUDE (-90 to +90):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 28.6139"
                      className="text-input font-mono"
                      value={inputLat}
                      onChange={(e) => setInputLat(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">LONGITUDE (-180 to +180):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 77.2090"
                      className="text-input font-mono"
                      value={inputLng}
                      onChange={(e) => setInputLng(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-row-grid">
                  <div className="form-group">
                    <label className="form-label">VIEWING HEADING (°):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="0 - 360"
                      className="text-input font-mono"
                      value={inputHeading}
                      onChange={(e) => setInputHeading(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">LOCATION DESCRIPTION:</label>
                    <input
                      type="text"
                      placeholder="Intersection description"
                      className="text-input font-mono"
                      value={inputDesc}
                      onChange={(e) => setInputDesc(e.target.value)}
                    />
                  </div>
                </div>

                {configMsg && (
                  <div className={`config-message ${configMsg.type === 'error' ? 'text-rose' : 'text-emerald'}`}>
                    {configMsg.text}
                  </div>
                )}

                <div className="modal-footer">
                  <button type="button" className="btn-secondary" onClick={() => setIsConfigOpen(false)}>
                    Close
                  </button>
                  <button type="submit" className="btn-primary" disabled={configSaving}>
                    {configSaving ? 'Saving Coordinates...' : 'Save & Map Node'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Error state if Google Maps script failed
  if (mapLoadError) {
    return (
      <div className="map-page-container">
        <div className="empty-state-card font-mono">
          <AlertTriangle size={42} className="text-rose" />
          <h3 className="empty-state-title">Google Maps API Error</h3>
          <p className="empty-state-desc">
            Failed to load Google Maps JavaScript API: {mapLoadError}. Ensure your API key has "Maps JavaScript API" enabled and billing/restrictions are valid.
          </p>
        </div>
      </div>
    );
  }

  // Empty state when absolutely no cameras have coordinates
  if (!hasGeoConfig) {
    return (
      <div className="map-page-container">
        <div className="empty-state-card font-mono">
          <MapPin size={42} className="text-muted" />
          <h3 className="empty-state-title">No Geographic Coordinates Configured</h3>
          <p className="empty-state-desc">
            All registered camera nodes currently lack valid WGS-84 coordinates. In accordance with strict municipal intelligence protocols, zero synthetic coordinates are invented.
          </p>
          <div className="empty-state-action-box">
            <button 
              type="button" 
              className="btn-primary"
              onClick={() => setIsConfigOpen(true)}
            >
              <Settings size={15} /> Configure Camera GPS Coordinates
            </button>
          </div>
        </div>

        {/* GPS Configuration Modal */}
        {isConfigOpen && (
          <div className="modal-backdrop">
            <div className="modal-dialog font-mono">
              <div className="modal-header">
                <span className="modal-title">GEOGRAPHIC COORDINATE CONFIGURATION</span>
                <button type="button" className="btn-icon" onClick={() => setIsConfigOpen(false)}>
                  <X size={16} />
                </button>
              </div>
              <form onSubmit={handleSaveLocation} className="modal-form">
                <div className="form-group">
                  <label className="form-label">SELECT CAMERA NODE:</label>
                  <select
                    className="select-input font-mono"
                    value={selectedCamForConfig}
                    onChange={(e) => setSelectedCamForConfig(e.target.value)}
                  >
                    {localCameras.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.id} — {c.name} {c.latitude ? `(${c.latitude.toFixed(4)}°N, ${c.longitude.toFixed(4)}°E)` : '[UNCONFIGURED]'}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row-grid">
                  <div className="form-group">
                    <label className="form-label">LATITUDE (-90 to +90):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 28.6139"
                      className="text-input font-mono"
                      value={inputLat}
                      onChange={(e) => setInputLat(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">LONGITUDE (-180 to +180):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 77.2090"
                      className="text-input font-mono"
                      value={inputLng}
                      onChange={(e) => setInputLng(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-row-grid">
                  <div className="form-group">
                    <label className="form-label">VIEWING HEADING (°):</label>
                    <input
                      type="number"
                      step="any"
                      placeholder="0 - 360"
                      className="text-input font-mono"
                      value={inputHeading}
                      onChange={(e) => setInputHeading(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">LOCATION DESCRIPTION:</label>
                    <input
                      type="text"
                      placeholder="Intersection description"
                      className="text-input font-mono"
                      value={inputDesc}
                      onChange={(e) => setInputDesc(e.target.value)}
                    />
                  </div>
                </div>

                {configMsg && (
                  <div className={`config-message ${configMsg.type === 'error' ? 'text-rose' : 'text-emerald'}`}>
                    {configMsg.text}
                  </div>
                )}

                <div className="modal-footer">
                  <button type="button" className="btn-secondary" onClick={() => setIsConfigOpen(false)}>
                    Close
                  </button>
                  <button type="submit" className="btn-primary" disabled={configSaving}>
                    {configSaving ? 'Saving Coordinates...' : 'Save & Map Node'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="map-page-container">
      {/* Missing coordinates alert ribbon if partial nodes unconfigured */}
      {unconfiguredCameras.length > 0 && (
        <div className="unconfigured-ribbon font-mono">
          <div className="ribbon-left">
            <AlertTriangle size={15} className="text-amber" />
            <span>
              <strong>{unconfiguredCameras.length} CAMERA NODE(S) UNMAPPED:</strong>{' '}
              {unconfiguredCameras.map((c) => c.id).join(', ')} lack GPS coordinates. Zero synthetic locations are rendered.
            </span>
          </div>
          <button 
            type="button" 
            className="btn-xs btn-secondary"
            onClick={() => setIsConfigOpen(true)}
          >
            Configure GPS
          </button>
        </div>
      )}

      {/* Top Filter & Layer Bar */}
      <div className="gis-filter-toolbar font-mono">
        <div className="gis-filter-left">
          <div className="filter-item">
            <Filter size={14} className="text-muted" />
            <span className="filter-label">TIME PRESET:</span>
            <div className="time-preset-pills">
              {(['15m', '1h', '6h', '24h', 'ALL'] as const).map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className={`preset-pill ${filters.time_range_preset === preset ? 'active' : ''}`}
                  onClick={() => setFilters((prev) => ({ ...prev, time_range_preset: preset }))}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-item">
            <span className="filter-label">CAMERA:</span>
            <select
              className="gis-select font-mono"
              value={filters.camera_id}
              onChange={(e) => setFilters((prev) => ({ ...prev, camera_id: e.target.value }))}
            >
              <option value="ALL">ALL NODES ({validCameras.length})</option>
              {validCameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} — {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-item">
            <span className="filter-label">VEHICLE:</span>
            <select
              className="gis-select font-mono"
              value={filters.vehicle_id}
              onChange={(e) => {
                const vid = e.target.value;
                setFilters((prev) => ({ ...prev, vehicle_id: vid }));
                const target = vehicles.find((v) => v.global_id === vid);
                if (target) onSelectVehicle(target);
              }}
            >
              <option value="ALL">-- INSPECT VEHICLE TRAJECTORY --</option>
              {vehicles.map((v) => (
                <option key={v.global_id} value={v.global_id}>
                  {v.global_id} {v.primary_plate ? `[${v.primary_plate}]` : ''} ({v.total_cameras_passed} Nodes)
                </option>
              ))}
            </select>
          </div>

          <div className="filter-item">
            <span className="filter-label">ALERT TYPE:</span>
            <select
              className="gis-select font-mono"
              value={filters.alert_type}
              onChange={(e) => setFilters((prev) => ({ ...prev, alert_type: e.target.value }))}
            >
              <option value="ALL">ALL ALERTS</option>
              <option value="BLACKLIST_MATCH">BLACKLIST MATCH</option>
              <option value="UNREGISTERED_PLATE">UNREGISTERED PLATE</option>
              <option value="CONGESTION_WARNING">CONGESTION WARNING</option>
              <option value="ANOMALOUS_SPEED">ANOMALOUS SPEED</option>
            </select>
          </div>
        </div>

        <div className="gis-filter-right">
          <button
            type="button"
            className="btn-xs btn-secondary"
            onClick={() => setIsConfigOpen(true)}
            title="Configure camera coordinates"
          >
            <Settings size={14} /> Node GPS
          </button>
        </div>
      </div>

      {/* Layer Toggles Strip */}
      <div className="gis-layer-toggles font-mono text-xs">
        <span className="layer-label">GIS LAYERS:</span>
        <button
          type="button"
          className={`layer-toggle-btn ${showCameras ? 'active' : ''}`}
          onClick={() => setShowCameras(!showCameras)}
        >
          {showCameras ? <Eye size={12} /> : <EyeOff size={12} />} Cameras ({validCameras.length})
        </button>
        <button
          type="button"
          className={`layer-toggle-btn ${showTrajectories ? 'active' : ''}`}
          onClick={() => setShowTrajectories(!showTrajectories)}
        >
          {showTrajectories ? <Eye size={12} /> : <EyeOff size={12} />} Trajectories
        </button>
        <button
          type="button"
          className={`layer-toggle-btn ${showCorridors ? 'active' : ''}`}
          onClick={() => setShowCorridors(!showCorridors)}
        >
          {showCorridors ? <Eye size={12} /> : <EyeOff size={12} />} Corridors
        </button>
        <button
          type="button"
          className={`layer-toggle-btn ${showDensityZones ? 'active' : ''}`}
          onClick={() => setShowDensityZones(!showDensityZones)}
        >
          {showDensityZones ? <Eye size={12} /> : <EyeOff size={12} />} Zone Density
        </button>
        <button
          type="button"
          className={`layer-toggle-btn ${showAlerts ? 'active' : ''}`}
          onClick={() => setShowAlerts(!showAlerts)}
        >
          {showAlerts ? <Eye size={12} /> : <EyeOff size={12} />} Alerts ({alerts.length})
        </button>
      </div>

      {/* Map Viewport Area */}
      <div className="map-layout">
        <div ref={mapContainerRef} className="map-gis-viewport" />

        {/* Floating Route Telemetry Card */}
        {currentVehicle && (
          <div className="map-floating-panel font-mono">
            <div className="floating-header">
              <span className="font-mono text-bold text-cyan">{currentVehicle.global_id}</span>
              <span className="badge badge-class">{currentVehicle.vehicle_class.toUpperCase()}</span>
            </div>

            <div className="floating-stat-row">
              <span className="text-muted">PLATE:</span>
              <span className="text-bold">{currentVehicle.primary_plate || 'UNRESOLVED'}</span>
            </div>

            <div className="floating-stat-row">
              <span className="text-muted">WAYPOINTS:</span>
              <span>{validWaypoints.length} Georeferenced ({currentVehicle.waypoints.length - validWaypoints.length} Unmapped)</span>
            </div>

            <div className="floating-stat-row">
              <span className="text-muted">FIRST SEEN:</span>
              <span>{currentVehicle.first_seen.substring(11, 19)} UTC</span>
            </div>

            <div className="floating-stat-row">
              <span className="text-muted">LAST SEEN:</span>
              <span>{currentVehicle.last_seen.substring(11, 19)} UTC</span>
            </div>

            <div className="floating-waypoint-list">
              {currentVehicle.waypoints.map((wp, idx) => {
                const isGeo = wp.latitude && wp.longitude;
                return (
                  <div key={idx} className={`floating-wp-item ${!isGeo ? 'wp-unmapped' : ''}`}>
                    <span className="wp-badge">#{idx + 1}</span>
                    <span className="wp-cam">{wp.camera_id}</span>
                    <span className="wp-time text-muted">{wp.timestamp_iso.substring(11, 19)} UTC</span>
                    {!isGeo && <span className="wp-missing">[NO GPS]</span>}
                  </div>
                );
              })}
            </div>

            <div className="floating-footer">
              <button
                type="button"
                className="btn-secondary text-xs"
                onClick={() => onNavigate('details')}
              >
                Inspect Full Dossier &rarr;
              </button>
            </div>
          </div>
        )}

        {/* Historical Trajectory Playback Control Bar */}
        {currentVehicle && validWaypoints.length > 1 && (
          <div className="playback-control-bar font-mono">
            <div className="playback-left">
              <button
                type="button"
                className="playback-btn-primary"
                onClick={() => setIsPlaying(!isPlaying)}
                title={isPlaying ? 'Pause Playback' : 'Play Historical Trajectory'}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              </button>

              <button
                type="button"
                className="playback-btn-secondary"
                onClick={() => {
                  setIsPlaying(false);
                  setPlaybackProgress(0);
                }}
                title="Reset Trajectory"
              >
                <RotateCcw size={14} />
              </button>

              <button
                type="button"
                className="playback-btn-secondary"
                onClick={() => {
                  setPlaybackProgress((prev) => Math.max(0, prev - 10));
                }}
                title="Step Backward"
              >
                <StepBack size={14} />
              </button>

              <button
                type="button"
                className="playback-btn-secondary"
                onClick={() => {
                  setPlaybackProgress((prev) => Math.min(100, prev + 10));
                }}
                title="Step Forward"
              >
                <StepForward size={14} />
              </button>

              <div className="speed-pills">
                {([1, 2, 5, 10] as const).map((spd) => (
                  <button
                    key={spd}
                    type="button"
                    className={`speed-pill ${playbackSpeed === spd ? 'active' : ''}`}
                    onClick={() => setPlaybackSpeed(spd)}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>

            <div className="playback-middle">
              <input
                type="range"
                min={0}
                max={100}
                step={0.5}
                value={playbackProgress}
                onChange={(e) => setPlaybackProgress(parseFloat(e.target.value))}
                className="playback-scrubber"
              />
            </div>

            <div className="playback-right">
              <span className="playback-progress-text">{playbackProgress.toFixed(0)}%</span>
              <span className="playback-vehicle-text">{currentVehicle.global_id}</span>
            </div>
          </div>
        )}
      </div>

      {/* GPS Configuration Modal Drawer */}
      {isConfigOpen && (
        <div className="modal-backdrop">
          <div className="modal-dialog font-mono">
            <div className="modal-header">
              <span className="modal-title">GEOGRAPHIC COORDINATE CONFIGURATION</span>
              <button type="button" className="btn-icon" onClick={() => setIsConfigOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleSaveLocation} className="modal-form">
              <div className="form-group">
                <label className="form-label">SELECT CAMERA NODE:</label>
                <select
                  className="select-input font-mono"
                  value={selectedCamForConfig}
                  onChange={(e) => setSelectedCamForConfig(e.target.value)}
                >
                  {localCameras.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} — {c.name} {c.latitude ? `(${c.latitude.toFixed(4)}°N, ${c.longitude.toFixed(4)}°E)` : '[UNCONFIGURED]'}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row-grid">
                <div className="form-group">
                  <label className="form-label">LATITUDE (-90 to +90):</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="e.g. 28.6139"
                    className="text-input font-mono"
                    value={inputLat}
                    onChange={(e) => setInputLat(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">LONGITUDE (-180 to +180):</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="e.g. 77.2090"
                    className="text-input font-mono"
                    value={inputLng}
                    onChange={(e) => setInputLng(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-row-grid">
                <div className="form-group">
                  <label className="form-label">VIEWING HEADING (°):</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="0 - 360"
                    className="text-input font-mono"
                    value={inputHeading}
                    onChange={(e) => setInputHeading(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">LOCATION DESCRIPTION:</label>
                  <input
                    type="text"
                    placeholder="Intersection description"
                    className="text-input font-mono"
                    value={inputDesc}
                    onChange={(e) => setInputDesc(e.target.value)}
                  />
                </div>
              </div>

              {configMsg && (
                <div className={`config-message ${configMsg.type === 'error' ? 'text-rose' : 'text-emerald'}`}>
                  {configMsg.text}
                </div>
              )}

              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setIsConfigOpen(false)}>
                  Close
                </button>
                <button type="submit" className="btn-primary" disabled={configSaving}>
                  {configSaving ? 'Saving Coordinates...' : 'Save & Map Node'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
