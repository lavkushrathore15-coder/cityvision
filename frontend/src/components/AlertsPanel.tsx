import React, { useState } from 'react';
import type { AlertItem } from '../types';
import { ShieldAlert, AlertTriangle, Info, CheckCircle, Clock, Check } from 'lucide-react';
import { updateAlertStatus } from '../services/api';

interface AlertsPanelProps {
  alerts: AlertItem[];
  onRefreshAlerts?: () => void;
}

export const AlertsPanel: React.FC<AlertsPanelProps> = ({ alerts, onRefreshAlerts }) => {
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const handleUpdateStatus = async (alertId: string, newStatus: string) => {
    setUpdatingId(alertId);
    try {
      await updateAlertStatus(alertId, newStatus, 'Command_Operator_402');
      if (onRefreshAlerts) onRefreshAlerts();
    } catch (e) {
      console.error('Failed to update alert status', e);
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredAlerts = alerts.filter((alert) => {
    // Category filter: blacklist, anomaly, congestion
    if (categoryFilter === 'blacklist') {
      const isBlacklist = alert.alert_type.includes('WATCHLIST') || alert.alert_type.includes('STOLEN');
      if (!isBlacklist) return false;
    } else if (categoryFilter === 'anomaly') {
      const isAnomaly = alert.alert_type.includes('TRANSIT') || alert.alert_type.includes('SPEED');
      if (!isAnomaly) return false;
    } else if (categoryFilter === 'congestion') {
      const isCongestion = alert.alert_type.includes('CONGESTION') || alert.alert_type.includes('DENSITY');
      if (!isCongestion) return false;
    }

    // Severity filter
    if (severityFilter !== 'ALL' && alert.severity.toUpperCase() !== severityFilter) {
      return false;
    }

    // Status filter
    if (statusFilter !== 'ALL') {
      const st = (alert.status || 'NEW').toUpperCase();
      if (st !== statusFilter) return false;
    }

    return true;
  });

  const getSeverityIcon = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return <ShieldAlert size={18} className="text-red" />;
      case 'HIGH':
      case 'WARNING':
        return <AlertTriangle size={18} className="text-amber" />;
      default:
        return <Info size={18} className="text-blue" />;
    }
  };

  return (
    <div className="alerts-page-container">
      {/* Alert Header & Filter Controls */}
      <div className="panel-card filter-bar-card">
        <div className="filter-controls-row">
          <div className="filter-group">
            <label className="filter-label font-mono">CATEGORY:</label>
            <select
              className="select-input font-mono"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="ALL">ALL CATEGORIES</option>
              <option value="blacklist">BLACKLIST / WATCHLIST MATCHES</option>
              <option value="anomaly">DRIVING & ROUTE ANOMALIES</option>
              <option value="congestion">CONGESTION & SPEED VIOLATIONS</option>
            </select>
          </div>

          <div className="filter-group">
            <label className="filter-label font-mono">SEVERITY:</label>
            <select
              className="select-input font-mono"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="ALL">ALL SEVERITIES</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>

          <div className="filter-group">
            <label className="filter-label font-mono">WORKFLOW STATUS:</label>
            <select
              className="select-input font-mono"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">ALL STATUSES</option>
              <option value="NEW">PENDING / NEW</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>
        </div>
      </div>

      {/* Summary Stat Pill Banner */}
      <div className="results-header-row">
        <span className="results-count font-mono text-sm">
          {filteredAlerts.length} INCIDENTS ACTIVE
        </span>
        <span className="text-muted text-xs font-mono">
          Consumes real alert generation pipeline &bull; Zero synthetic alerts injected
        </span>
      </div>

      {/* Alerts Feed List */}
      <div className="alerts-feed-wrapper">
        {filteredAlerts.length === 0 ? (
          <div className="empty-state-card">
            <CheckCircle size={32} className="text-emerald" />
            <h3 className="empty-state-title">No Incident Alerts Matching Criteria</h3>
            <p className="empty-state-desc">
              Alerts appear only when the backend intelligence pipeline triggers a watchlist hit, transit anomaly, or speed violation.
            </p>
          </div>
        ) : (
          <div className="alerts-stack">
            {filteredAlerts.map((alert) => {
              const alertId = alert.id || alert.alert_id || 'ALT-000';
              const alertStatus = (alert.status || 'NEW').toUpperCase();

              return (
                <div
                  key={alertId}
                  className={`alert-card-detailed severity-${alert.severity.toLowerCase()} status-${alertStatus.toLowerCase()}`}
                >
                  <div className="alert-card-left">
                    <div className="alert-icon-wrap">
                      {getSeverityIcon(alert.severity)}
                    </div>
                  </div>

                  <div className="alert-card-body">
                    <div className="alert-top-meta">
                      <span className={`badge badge-severity-${alert.severity.toLowerCase()}`}>
                        {alert.severity}
                      </span>
                      <span className="badge badge-alert-type font-mono">{alert.alert_type}</span>
                      <span className="alert-timestamp font-mono text-muted text-xs">
                        <Clock size={12} /> {alert.timestamp_iso.substring(0, 19).replace('T', ' ')} UTC
                      </span>
                      <span className={`badge status-pill-${alertStatus.toLowerCase()}`}>
                        {alertStatus}
                      </span>
                    </div>

                    <h4 className="alert-main-title">{alert.message}</h4>

                    <div className="alert-meta-details font-mono text-xs">
                      <span>CCTV NODE: <strong className="text-cyan">{alert.camera_id}</strong></span>
                      {alert.plate_text && (
                        <span>
                          FLAGGED PLATE: <strong className="plate-badge">{alert.plate_text}</strong>
                        </span>
                      )}
                      {alert.global_vehicle_id && (
                        <span>
                          VEHICLE ID: <strong>{alert.global_vehicle_id}</strong>
                        </span>
                      )}
                      {alert.acknowledged_by && (
                        <span className="text-muted">
                          OPERATOR: {alert.acknowledged_by}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="alert-card-actions">
                    {alertStatus === 'NEW' && (
                      <button
                        type="button"
                        className="btn-action-primary"
                        disabled={updatingId === alertId}
                        onClick={() => handleUpdateStatus(alertId, 'ACKNOWLEDGED')}
                      >
                        <Check size={13} />
                        <span>Acknowledge</span>
                      </button>
                    )}

                    {alertStatus === 'ACKNOWLEDGED' && (
                      <button
                        type="button"
                        className="btn-action-resolve"
                        disabled={updatingId === alertId}
                        onClick={() => handleUpdateStatus(alertId, 'RESOLVED')}
                      >
                        <CheckCircle size={13} />
                        <span>Resolve</span>
                      </button>
                    )}

                    {alertStatus === 'RESOLVED' && (
                      <span className="resolved-check font-mono text-xs text-emerald">
                        ✓ Case Closed
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
