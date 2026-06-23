import React from 'react'
import Map, { Source, Layer, Marker } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getScoreColor } from '../utils/helpers'
import DetailPopup from './DetailPopup'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

export default function MapView({
    mapRef, 
    ntaGeojson,
    recommendations,
    selectedNta,
    userLocation,
    popupInfo,
    selectedDetail,
    loadingDetail,
    onMapClick,
    onPopupClose
}) {
    const scoredGeojson = React.useMemo(() => {
        if (!ntaGeojson?.features?.length) return null

        const scoreMap = {}
        if (Array.isArray(recommendations)) {
          recommendations.forEach(r => { scoreMap[r.ntaname] = r })
        }

        return {
          ...ntaGeojson,
          features: ntaGeojson.features.map(f => {
            const rec = scoreMap[f.properties?.ntaname]
            return {
              ...f,
              properties: {
                ...f.properties,
                score: rec?.score ?? 0,
                label: rec?.label ?? 'Poor',
                color: rec ? getScoreColor(rec.label) : '#374151',
              }
            }
          })
        }
      }, [ntaGeojson, recommendations])

      const hasScoreLayer = Array.isArray(recommendations) && recommendations.length > 0

      return (
        <div className="map-container">
          <Map
            ref={mapRef}
            initialViewState={{ longitude: -73.95, latitude: 40.73, zoom: 11 }}
            style={{ width: '100%', height: '100%' }}
            mapStyle={MAP_STYLE}
            interactiveLayerIds={hasScoreLayer ? ['nta-fill'] : []}
            onClick={onMapClick}
            onLoad={(e) => e.target.resize()}
          >
            {scoredGeojson && (
              <Source id="nta" type="geojson" data={scoredGeojson}>
                <Layer
                  id="nta-fill"
                  type="fill"
                  paint={{
                    'fill-color': ['get', 'color'],
                    'fill-opacity': [
                      'case',
                      ['==', ['get', 'ntaname'], selectedNta ?? ''], 0.85,
                      0.5
                    ]
                  }}
                />
                <Layer
                  id="nta-border"
                  type="line"
                  paint={{
                    'line-color': [
                      'case',
                      ['==', ['get', 'ntaname'], selectedNta ?? ''], '#FFFFFF',
                      'rgba(255,255,255,0.15)'
                    ],
                    'line-width': [
                      'case',
                      ['==', ['get', 'ntaname'], selectedNta ?? ''], 2,
                      0.5
                    ]
                  }}
                />
              </Source>
            )}
     
            {userLocation && Number.isFinite(userLocation.lng) && Number.isFinite(userLocation.lat) && (
              <Marker longitude={userLocation.lng} latitude={userLocation.lat}>
                <div className="user-dot" />
              </Marker>
            )}
     
            <DetailPopup
              popupInfo={popupInfo}
              detail={selectedDetail}
              loading={loadingDetail}
              onClose={onPopupClose}
            />
          </Map>
     
          <div className="legend">
            {[['Great','#22C55E'],['Good','#3B82F6'],['Fair','#F59E0B'],['Poor','#EF4444']].map(([label, color]) => (
              <div key={label} className="legend-item">
                <div className="legend-dot" style={{ background: color }} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )   
}