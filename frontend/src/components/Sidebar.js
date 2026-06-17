import React from 'react'
import { getScoreColor, haversineDistance, DISTANCE_OPTIONS, PRESET_ACTIVITIES } from '../utils/helpers'

export default function Sidebar({
  recommendations,
  loading,
  activity,
  isCustomMode,
  customInput,
  selectedNta,
  userLocation,
  distanceFilter,
  onDistanceChange,
  onNeighborhoodClick,
}) {
  const currentActivity = PRESET_ACTIVITIES.find(a => a.key === activity)

  const topNeighborhoods = React.useMemo(() => {
    let filtered = [...recommendations].sort((a, b) => b.score - a.score)
    if (distanceFilter && userLocation) {
      filtered = filtered.filter(r => {
        if (!r.latitude || !r.longitude) return false
        const d = haversineDistance(userLocation.lat, userLocation.lng, r.latitude, r.longitude)
        return d <= distanceFilter
      })
    }
    return filtered.slice(0, 10)
  }, [recommendations, distanceFilter, userLocation])

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2 className="sidebar-title">
          Top {topNeighborhoods.length} {isCustomMode ? `"${customInput}"` : (currentActivity?.label ?? '')}
        </h2>
        <div className="distance-filters">
          {DISTANCE_OPTIONS.map(opt => (
            <button
              key={opt.label}
              className={`dist-btn ${distanceFilter === opt.miles ? 'dist-active' : ''}`}
              onClick={() => onDistanceChange(opt.miles)}
              disabled={!userLocation && opt.miles !== null}
              title={!userLocation && opt.miles !== null ? 'Enable location to filter by distance' : ''}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="loading-list">Loading neighborhoods...</div>
      ) : (
        <ul className="neighborhood-list">
          {topNeighborhoods.map((rec, i) => {
            const dist = userLocation && rec.latitude && rec.longitude
              ? haversineDistance(userLocation.lat, userLocation.lng, rec.latitude, rec.longitude).toFixed(1)
              : null

            return (
              <li
                key={rec.ntaname}
                className={`neighborhood-item ${selectedNta === rec.ntaname ? 'neighborhood-item-active' : ''}`}
                onClick={() => onNeighborhoodClick(rec)}
              >
                <div className="rank">{i + 1}</div>
                <div className="neighborhood-info">
                  <div className="neighborhood-name">{rec.ntaname}</div>
                  <div className="neighborhood-meta">
                    <span className="score-badge" style={{ background: getScoreColor(rec.label) }}>
                      {rec.label}
                    </span>
                    <span className="score-num">{rec.score}</span>
                    {dist && <span className="dist">{dist}mi</span>}
                    {rec.has_major_event === 1 && <span className="event-chip">📅 Event</span>}
                  </div>
                  {rec.summary && <div className="summary">{rec.summary}</div>}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}