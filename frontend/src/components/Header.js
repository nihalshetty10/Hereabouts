import React from 'react'
import { PRESET_ACTIVITIES } from '../utils/helpers'

export default function Header({
  activity,
  onActivityChange,
  customInput,
  onCustomInputChange,
  onCustomSubmit,
  customLoading,
  lastUpdated,
  isCustomMode,
}) {
  return (
    <header className="header">
      <div className="header-left">
        <span className="logo">vybe</span>
        {lastUpdated && (
          <span className="last-updated">
            Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      <div className="header-right">
        <div className="activity-pills">
          {PRESET_ACTIVITIES.map(a => (
            <button
              key={a.key}
              className={`pill ${activity === a.key && !isCustomMode ? 'pill-active' : ''}`}
              onClick={() => onActivityChange(a.key)}
            >
              {a.emoji} {a.label}
            </button>
          ))}
        </div>

        <div className="custom-input-row">
          <input
            className="custom-input"
            placeholder="Or type your own activity..."
            value={customInput}
            onChange={e => onCustomInputChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onCustomSubmit()}
          />
          <button
            className="custom-btn"
            onClick={onCustomSubmit}
            disabled={customLoading}
          >
            {customLoading ? '...' : '→'}
          </button>
        </div>
      </div>
    </header>
  )
}