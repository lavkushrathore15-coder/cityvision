import React, { useEffect, useState } from 'react';
import type { 
  TrafficMetrics, 
  CameraNode, 
  TrafficCounts, 
  CameraActivityItem, 
  ZoneDensityItem, 
  CongestionItem 
} from '../types';
import { 
  BarChart3, 
  Activity, 
  Gauge, 
  TrendingUp, 
  MapPin, 
  ArrowRight,
} from 'lucide-react';
import { 
  fetchTrafficCounts, 
  fetchCameraActivity, 
  fetchZoneDensity, 
  fetchCongestion 
} from '../services/api';

interface AnalyticsViewProps {
  metrics: TrafficMetrics;
  cameras: CameraNode[];
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({ metrics, cameras }) => {
  const [trafficCounts, setTrafficCounts] = useState<TrafficCounts | null>(null);
  const [cameraActivity, setCameraActivity] = useState<CameraActivityItem[]>([]);
  const [zoneDensity, setZoneDensity] = useState<ZoneDensityItem[]>([]);
  const [congestion, setCongestion] = useState<{ corridors: CongestionItem[]; index: number } | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([
      fetchTrafficCounts(),
      fetchCameraActivity(),
      fetchZoneDensity(),
      fetchCongestion(),
    ]).then(([countsRes, camRes, zoneRes, congRes]) => {
      if (!isMounted) return;

      if (countsRes.status === 'fulfilled') {
        setTrafficCounts(countsRes.value);
      } else {
        setTrafficCounts(null);
      }

      if (camRes.status === 'fulfilled') {
        setCameraActivity(camRes.value.cameras);
      } else {
        setCameraActivity([]);
      }

      if (zoneRes.status === 'fulfilled') {
        setZoneDensity(zoneRes.value.zones);
      } else {
        setZoneDensity([]);
      }

      if (congRes.status === 'fulfilled') {
        setCongestion({
          corridors: congRes.value.corridors,
          index: congRes.value.citywide_congestion_index_percent,
        });
      } else {
        setCongestion(null);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [cameras.length, metrics.congestion_index_percent]);

  const hourlyCounts = trafficCounts?.hourly_vehicle_counts || metrics.hourly_vehicle_counts;
  const maxHourly = Math.max(...hourlyCounts, 10);

  return (
    <div className="analytics-page-container">
      {/* KPI Overview Strip */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">TOTAL TRACKED VEHICLES</span>
            <Activity size={16} className="kpi-icon" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{trafficCounts?.total_tracked_vehicles ?? metrics.total_tracked_vehicles}</span>
            <span className="kpi-unit">Identified Identities</span>
          </div>
          <div className="kpi-footer font-mono text-xs text-muted">
            Total Observations: {trafficCounts?.total_observations_recorded ?? 0}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">ACTIVE SENSOR COVERAGE</span>
            <MapPin size={16} className="kpi-icon text-emerald" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{cameras.length} / {cameras.length}</span>
            <span className="kpi-unit">CCTV Grid Nodes</span>
          </div>
          <div className="kpi-footer font-mono text-xs text-emerald">
            ● 100% Sensors Reporting Telemetry
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">CITY CONGESTION INDEX</span>
            <Gauge size={16} className="kpi-icon text-amber" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">
              {(congestion?.index ?? metrics.congestion_index_percent).toFixed(1)}%
            </span>
            <span className="kpi-unit">Transit Delay Metric</span>
          </div>
          <div className="kpi-footer font-mono text-xs text-muted">
            Baseline Free-Flow Speed: 50 km/h
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">MEAN ARTERIAL SPEED</span>
            <TrendingUp size={16} className="kpi-icon text-cyan" />
          </div>
          <div className="kpi-main">
            <span className="kpi-value">{(metrics.average_speed_kmh || 0).toFixed(1)}</span>
            <span className="kpi-unit">km/h City Average</span>
          </div>
          <div className="kpi-footer font-mono text-xs text-muted">
            Derived from Camera-to-Camera Hops
          </div>
        </div>
      </div>

      {/* 2-Column Analytics Layout */}
      <div className="dashboard-columns">
        {/* Left Column: Hourly Histogram & Sensor Activity */}
        <div className="dashboard-col">
          {/* Hourly Traffic Flow Histogram */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <BarChart3 size={16} />
                <h3 className="panel-title">24-Hour Traffic Volume Distribution</h3>
              </div>
              <span className="font-mono text-xs text-muted">OBSERVATION TIMESTAMPS</span>
            </div>

            <div className="histogram-wrapper">
              <div className="histogram-bars">
                {hourlyCounts.map((count, hr) => {
                  const heightPct = Math.max((count / maxHourly) * 100, 3);
                  return (
                    <div key={hr} className="hist-col" title={`${hr}:00 UTC - ${count} vehicle passes`}>
                      <div className="hist-bar-container">
                        <div 
                          className="hist-bar-fill" 
                          style={{ height: `${heightPct}%` }}
                        />
                      </div>
                      <span className="hist-label font-mono">{hr}</span>
                    </div>
                  );
                })}
              </div>
              <div className="hist-x-axis font-mono text-xs text-muted">
                <span>00:00 UTC</span>
                <span>06:00 UTC</span>
                <span>12:00 UTC</span>
                <span>18:00 UTC</span>
                <span>23:00 UTC</span>
              </div>
            </div>
          </div>

          {/* Camera Sensor Activity Breakdown */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <Activity size={16} />
                <h3 className="panel-title">CCTV Sensor Node Observation Activity</h3>
              </div>
            </div>

            <div className="table-responsive">
              {cameraActivity.length === 0 ? (
                <div className="p-6 text-center text-muted font-mono text-xs">
                  No camera observation activity recorded in database.
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>CAMERA ID</th>
                      <th>NODE NAME</th>
                      <th>TOTAL PASSES</th>
                      <th>UNIQUE VEHICLES</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cameraActivity.map((cam) => (
                      <tr key={cam.camera_id}>
                        <td className="font-mono text-bold">{cam.camera_id}</td>
                        <td>{cam.camera_name}</td>
                        <td className="font-mono text-center">{cam.total_observations}</td>
                        <td className="font-mono text-center">{cam.unique_vehicles_observed}</td>
                        <td>
                          <span className="status-pill status-active">ACTIVE</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Corridor Congestion & Zone Density */}
        <div className="dashboard-col">
          {/* Corridor Congestion Analysis */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <ArrowRight size={16} />
                <h3 className="panel-title">Corridor Transit Speed & Congestion Delay</h3>
              </div>
            </div>

            <div className="table-responsive">
              {!congestion || congestion.corridors.length === 0 ? (
                <div className="p-6 text-center text-muted font-mono text-xs">
                  No multi-camera corridor transitions recorded yet.
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>CORRIDOR LINK</th>
                      <th>DISTANCE</th>
                      <th>AVG SPEED</th>
                      <th>DELAY RATIO</th>
                      <th>FLOW TIER</th>
                    </tr>
                  </thead>
                  <tbody>
                    {congestion.corridors.map((corr, idx) => (
                      <tr key={idx}>
                        <td className="font-mono text-xs">
                          {corr.from_camera_id} &rarr; {corr.to_camera_id}
                        </td>
                        <td className="font-mono text-xs">
                          {corr.distance_meters ? `${corr.distance_meters.toFixed(0)}m` : 'N/A'}
                        </td>
                        <td className="font-mono text-bold text-sm">
                          {corr.average_transit_speed_kmh ? `${corr.average_transit_speed_kmh.toFixed(1)} km/h` : 'N/A'}
                        </td>
                        <td className="font-mono text-sm">
                          {corr.delay_ratio.toFixed(2)}x
                        </td>
                        <td>
                          <span className={`badge badge-congestion-${corr.congestion_level.toLowerCase()}`}>
                            {corr.congestion_level.replace('_', ' ')}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Spatial Zone Density Indicators */}
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title-group">
                <MapPin size={16} />
                <h3 className="panel-title">Camera Zone Spatial Density</h3>
              </div>
            </div>

            <div className="zone-density-stack">
              {zoneDensity.length === 0 ? (
                <div className="p-6 text-center text-muted font-mono text-xs">
                  No spatial density observations available.
                </div>
              ) : (
                zoneDensity.map((zone) => (
                  <div key={zone.camera_id} className="zone-density-row font-mono">
                    <div className="zone-info">
                      <span className="zone-id text-bold">{zone.camera_id}</span>
                      <span className="zone-name text-muted text-xs">{zone.zone_name}</span>
                    </div>

                    <div className="zone-bar-area">
                      <div className="zone-bar-bg">
                        <div 
                          className={`zone-bar-fill level-${zone.density_level.toLowerCase()}`}
                          style={{ width: `${Math.min(zone.active_vehicle_density * 5, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div className="zone-metric">
                      <span className="zone-density-val">{zone.active_vehicle_density} veh/hr</span>
                      <span className={`badge badge-density-${zone.density_level.toLowerCase()}`}>
                        {zone.density_level}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
