import React, { useState, useEffect } from 'react';
import type { ActiveTab } from '../types';
import { 
  LayoutDashboard, 
  Cctv, 
  Search, 
  MapPin, 
  Bell, 
  BarChart3, 
  FileText,
  Activity,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

interface NavbarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  alertCount: number;
  isDemoMode: boolean;
  systemMode?: 'real' | 'demo';
  onToggleMode?: (mode: 'real' | 'demo') => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ 
  activeTab, 
  setActiveTab, 
  alertCount, 
  isDemoMode,
  systemMode = 'real',
  onToggleMode,
  onRefresh,
  isRefreshing = false,
}) => {
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setCurrentTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  const navItems: { id: ActiveTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: 'dashboard', label: 'Overview', icon: <LayoutDashboard size={15} /> },
    { id: 'cameras', label: 'Cameras', icon: <Cctv size={15} /> },
    { id: 'search', label: 'Vehicles', icon: <Search size={15} /> },
    ...(activeTab === 'details' ? [{ id: 'details' as ActiveTab, label: 'Vehicle Details', icon: <FileText size={15} /> }] : []),
    { id: 'map', label: 'Trajectories', icon: <MapPin size={15} /> },
    { id: 'alerts', label: 'Alerts', icon: <Bell size={15} />, badge: alertCount },
    { id: 'analytics', label: 'Analytics', icon: <BarChart3 size={15} /> },
  ];

  return (
    <header className="navbar">
      <div className="nav-brand">
        <div className="brand-crest">
          <Activity size={17} className="crest-icon" />
        </div>
        <div className="brand-titles">
          <div className="brand-row">
            <span className="brand-name">CITYVISION AI</span>
            <span className="brand-tag">SIH26127</span>
          </div>
          <span className="brand-subtitle">CITY-WIDE VEHICLE INTELLIGENCE</span>
          <div className="pipeline-flow-banner font-mono" aria-label="Pipeline Architecture: Detect, Identify, Track, Understand, Act">
            <span className="flow-step">DETECT</span>
            <span className="flow-sep">&bull;</span>
            <span className="flow-step">IDENTIFY</span>
            <span className="flow-sep">&bull;</span>
            <span className="flow-step">TRACK</span>
            <span className="flow-sep">&bull;</span>
            <span className="flow-step">UNDERSTAND</span>
            <span className="flow-sep">&bull;</span>
            <span className="flow-step">ACT</span>
          </div>
        </div>
      </div>

      <nav className="nav-menu" aria-label="Primary Navigation">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            {item.icon}
            <span>{item.label}</span>
            {item.badge !== undefined && item.badge > 0 && (
              <span className="badge badge-alert">{item.badge}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="nav-status-group">
        {/* Interactive Mode Switcher: REAL / LOCAL PROCESSING <-> DEMO MODE */}
        {onToggleMode && (
          <div className="mode-segmented-toggle" role="group" aria-label="System Mode Switcher">
            <button
              type="button"
              className={`toggle-option ${systemMode === 'real' ? 'active real-active' : ''}`}
              onClick={() => onToggleMode('real')}
              title="Process live local video feeds and production DB"
            >
              <span className="mode-indicator-dot live-dot"></span>
              <span>REAL PROCESSING</span>
            </button>
            <button
              type="button"
              className={`toggle-option ${systemMode === 'demo' ? 'active demo-active' : ''}`}
              onClick={() => onToggleMode('demo')}
              title="Activate isolated 11-stage DEMO MODE (data/cityvision_demo.db)"
            >
              <span className="mode-indicator-dot demo-dot"></span>
              <span>DEMO MODE</span>
            </button>
          </div>
        )}

        {isDemoMode || systemMode === 'demo' ? (
          <div className="status-badge demo-badge" title="Operating in isolated DEMO sandbox. Zero records in production DB.">
            <AlertTriangle size={13} />
            <span>DEMO ACTIVE</span>
          </div>
        ) : (
          <div className="status-badge live-badge" title="Live FastAPI backend connected at port 8000">
            <span className="pulse-dot"></span>
            <span>LIVE BACKEND</span>
          </div>
        )}

        <div className="clock-display" title="Coordinated Universal Time">
          {currentTime}
        </div>

        {onRefresh && (
          <button 
            type="button" 
            className={`btn-icon-refresh ${isRefreshing ? 'spinning' : ''}`} 
            onClick={onRefresh}
            title="Refresh active telemetry"
            disabled={isRefreshing}
          >
            <RefreshCw size={14} />
          </button>
        )}
      </div>
    </header>
  );
};
