import React from 'react'
import { Popup } from 'react-map-gl'
import { getScoreColor } from '../utils/helpers'

export default function DetailPopup({ popupInfo, detail, loading, onClose }) {
  if (!popupInfo || !detail) return null

  return (
    <Popup
      longitude={popupInfo.lng}
      latitude={popupInfo.lat}
      anchor="bottom"
      onClose={onClose}
      maxWidth="320px"
    >
      <div className="popup-content">
        <div className="popup-header">
          <span className="popup-name">{detail.ntaname}</span>
          <span
            className="popup-badge"
            style={{ background: getScoreColor(detail.label) }}
          >
            {detail.label} · {detail.score}
          </span>
        </div>

        {loading ? (
          <div className="popup-loading">Analyzing neighborhood...</div>
        ) : (
          <>
            {detail.summary && (
              <p className="popup-summary">{detail.summary}</p>
            )}

            {detail.pros && (
              <div className="popup-section">
                <span className="popup-label">Pros</span>
                {detail.pros.split(' | ').map((p, i) => (
                  <div key={i} className="popup-pro">✓ {p}</div>
                ))}
              </div>
            )}

            {detail.cons && (
              <div className="popup-section">
                <span className="popup-label">Cons</span>
                <div className="popup-con">✗ {detail.cons}</div>
              </div>
            )}

            {detail.nearby_event_titles && detail.nearby_event_titles !== '0' && (
              <div className="popup-section">
                <span className="popup-label">Nearby Events</span>
                <div className="popup-events">
                  {detail.nearby_event_titles.split(', ').slice(0, 3).map((e, i) => (
                    <div key={i} className="event-tag">📅 {e}</div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Popup>
  )
}