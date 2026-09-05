import React, { useState } from 'react';
import type { GlobalVehicle, ActiveTab } from '../types';
import { Search, AlertCircle, MapPin, FileText, X } from 'lucide-react';
import { searchVehicles } from '../services/api';

interface VehicleSearchProps {
  vehicles: GlobalVehicle[];
  onSelectVehicle: (v: GlobalVehicle) => void;
  onNavigate: (tab: ActiveTab) => void;
}

export const VehicleSearch: React.FC<VehicleSearchProps> = ({
  vehicles,
  onSelectVehicle,
  onNavigate,
}) => {
  const [plateQuery, setPlateQuery] = useState('');
  const [classFilter, setClassFilter] = useState('ALL');
  const [flagFilter, setFlagFilter] = useState('ALL');
  const [searchResults, setSearchResults] = useState<GlobalVehicle[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!plateQuery.trim() && classFilter === 'ALL' && flagFilter === 'ALL') {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    try {
      const results = await searchVehicles({
        plate: plateQuery.trim() || undefined,
        vehicle_class: classFilter !== 'ALL' ? classFilter : undefined,
      });
      setSearchResults(results);
    } catch {
      // Local filter fallback
      const filtered = vehicles.filter((v) => {
        const matchesPlate = !plateQuery || (v.primary_plate && v.primary_plate.toLowerCase().includes(plateQuery.toLowerCase()));
        const matchesClass = classFilter === 'ALL' || v.vehicle_class.toLowerCase() === classFilter.toLowerCase();
        const matchesFlag = flagFilter === 'ALL' || (flagFilter === 'FLAGGED' ? v.is_flagged : !v.is_flagged);
        return matchesPlate && matchesClass && matchesFlag;
      });
      setSearchResults(filtered);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClear = () => {
    setPlateQuery('');
    setClassFilter('ALL');
    setFlagFilter('ALL');
    setSearchResults(null);
  };

  const displayedVehicles = searchResults !== null ? searchResults : vehicles;

  return (
    <div className="search-page-container">
      {/* Search Header & Filter Controls */}
      <div className="panel-card search-filter-card">
        <form onSubmit={handleSearch} className="search-form">
          <div className="search-input-group">
            <Search size={16} className="search-icon text-muted" />
            <input
              type="text"
              className="search-input"
              placeholder="Search by license plate number (e.g. RJ14AB1234)..."
              value={plateQuery}
              onChange={(e) => setPlateQuery(e.target.value)}
            />
            {plateQuery && (
              <button type="button" className="btn-icon-clear" onClick={() => setPlateQuery('')}>
                <X size={14} />
              </button>
            )}
          </div>

          <div className="search-controls-row">
            <div className="filter-group">
              <label className="filter-label font-mono">VEHICLE CLASS:</label>
              <select
                className="select-input font-mono"
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
              >
                <option value="ALL">ALL CLASSES</option>
                <option value="car">CAR</option>
                <option value="bus">BUS</option>
                <option value="truck">TRUCK</option>
                <option value="motorcycle">MOTORCYCLE</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label font-mono">WATCHLIST STATUS:</label>
              <select
                className="select-input font-mono"
                value={flagFilter}
                onChange={(e) => setFlagFilter(e.target.value)}
              >
                <option value="ALL">ALL VEHICLES</option>
                <option value="FLAGGED">FLAGGED ONLY</option>
                <option value="CLEAN">UNFLAGGED</option>
              </select>
            </div>

            <div className="search-btn-group">
              <button type="submit" className="btn-primary" disabled={isSearching}>
                {isSearching ? 'SEARCHING...' : 'APPLY FILTERS'}
              </button>
              {(plateQuery || classFilter !== 'ALL' || flagFilter !== 'ALL') && (
                <button type="button" className="btn-secondary" onClick={handleClear}>
                  RESET
                </button>
              )}
            </div>
          </div>
        </form>
      </div>

      {/* Results Meta Banner */}
      <div className="results-header-row">
        <span className="results-count font-mono text-sm">
          {displayedVehicles.length} {displayedVehicles.length === 1 ? 'RECORD' : 'RECORDS'} MATCHED
        </span>
        <span className="text-muted text-xs">
          Chronologically sorted by last camera detection (UTC)
        </span>
      </div>

      {/* Results Table */}
      <div className="panel-card table-panel">
        {displayedVehicles.length === 0 ? (
          <div className="empty-state-card">
            <AlertCircle size={28} className="text-muted" />
            <p className="empty-state-title">No matching vehicles found</p>
            <p className="empty-state-desc">
              Try broadening your query parameters or clearing filters.
            </p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>GLOBAL VEHICLE ID</th>
                  <th>DETECTED LICENSE PLATE</th>
                  <th>CLASS</th>
                  <th>CAMERAS PASSED</th>
                  <th>FIRST DETECTED</th>
                  <th>LAST DETECTED</th>
                  <th>WATCHLIST</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {displayedVehicles.map((veh) => (
                  <tr key={veh.global_id} className={veh.is_flagged ? 'row-flagged' : ''}>
                    <td className="font-mono text-bold">{veh.global_id}</td>
                    <td>
                      {veh.primary_plate ? (
                        <span className="plate-badge">{veh.primary_plate}</span>
                      ) : (
                        <span className="text-muted text-xs italic">Plate Unresolved</span>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-class">{veh.vehicle_class.toUpperCase()}</span>
                    </td>
                    <td className="text-center font-mono">
                      {veh.total_cameras_passed} Nodes
                    </td>
                    <td className="font-mono text-muted text-xs">
                      {veh.first_seen.substring(0, 19).replace('T', ' ')} UTC
                    </td>
                    <td className="font-mono text-muted text-xs">
                      {veh.last_seen.substring(0, 19).replace('T', ' ')} UTC
                    </td>
                    <td>
                      {veh.is_flagged ? (
                        <span className="badge badge-flagged">FLAGGED</span>
                      ) : (
                        <span className="badge badge-clear">NORMAL</span>
                      )}
                    </td>
                    <td>
                      <div className="action-buttons-group">
                        <button
                          type="button"
                          className="btn-action-small"
                          onClick={() => {
                            onSelectVehicle(veh);
                            onNavigate('details');
                          }}
                          title="Inspect vehicle timeline & match evidence"
                        >
                          <FileText size={12} />
                          <span>Details</span>
                        </button>
                        <button
                          type="button"
                          className="btn-action-small"
                          onClick={() => {
                            onSelectVehicle(veh);
                            onNavigate('map');
                          }}
                          title="View route trajectory on GIS map"
                        >
                          <MapPin size={12} />
                          <span>Map</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
