import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import MapView from './components/MapView'
import useRecommendations from './hooks/useRecommendations'
import { buildCentroidMap, enrichWithCentroids } from './utils/helpers'
import './App.css'

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000'
const NTA_GEOJSON_URL = 'https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON'

export default function App() {
  const [activity, setActivity]             = useState('night_out')
  const [customInput, setCustomInput]       = useState('')
  const [isCustomMode, setIsCustomMode]     = useState(false)
  const [customLoading, setCustomLoading]   = useState(false)
  const [ntaGeojson, setNtaGeojson]         = useState(null)
  const [selectedNta, setSelectedNta]       = useState(null)
  const [selectedDetail, setSelectedDetail] = useState(null)
  const [loadingDetail, setLoadingDetail]   = useState(false)
  const [popupInfo, setPopupInfo]           = useState(null)
  const [userLocation, setUserLocation]     = useState(null)
  const [distanceFilter, setDistanceFilter] = useState(null)

  const mapRef = useRef()

  const { recommendations, loading, updateNeighborhood } =
    useRecommendations(isCustomMode ? null : activity)

  const enrichedRecommendations = React.useMemo(() => {
    const centroidMap = buildCentroidMap(ntaGeojson)
    return enrichWithCentroids(recommendations, centroidMap)
  }, [recommendations, ntaGeojson])

  // get user location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => setUserLocation(null)
      )
    }
  }, [])

  // fetch NTA boundaries once
  useEffect(() => {
    fetch(NTA_GEOJSON_URL)
      .then(r => r.json())
      .then(data => {
        if (data?.type === 'FeatureCollection' && Array.isArray(data.features)) {
          setNtaGeojson(data)
        } else {
          console.error('Unexpected NTA GeoJSON response:', data)
        }
      })
      .catch(console.error)
  }, [])

  const handleActivityChange = (key) => {
    setActivity(key)
    setIsCustomMode(false)
    setSelectedNta(null)
    setSelectedDetail(null)
    setPopupInfo(null)
  }

  const handleCustomSubmit = async () => {
    if (!customInput.trim()) return
    setCustomLoading(true)
    try {
      const res = await axios.post(`${API_URL}/recommendations/custom`, {
        activity: customInput.trim()
      })
      updateNeighborhood('__replace__', res.data)
      setIsCustomMode(true)
    } catch (e) {
      if (e.response?.status === 429) alert('Custom activity limit: 1 request per day.')
      else alert('Failed to score custom activity. Try again.')
    } finally {
      setCustomLoading(false)
    }
  }

  const handleMapClick = async (e) => {
    const features = e.features
    if (!features?.length) {
      setSelectedNta(null)
      setSelectedDetail(null)
      setPopupInfo(null)
      return
    }
    const ntaname = features[0].properties?.ntaname
    if (!ntaname) return

    const rec = enrichedRecommendations.find(r => r.ntaname === ntaname)
    setSelectedNta(ntaname)
    setSelectedDetail(rec || null)
    setPopupInfo({ lng: e.lngLat.lng, lat: e.lngLat.lat })

    if (rec && !rec.summary) {
      setLoadingDetail(true)
      try {
        const res = await axios.get(
          `${API_URL}/neighborhoods/${encodeURIComponent(ntaname)}`,
          { params: { activity: isCustomMode ? customInput : activity } }
        )
        setSelectedDetail(res.data)
        updateNeighborhood(ntaname, res.data)
      } catch (e) {
        console.error('Failed to load neighborhood detail:', e)
      } finally {
        setLoadingDetail(false)
      }
    }
  }

  const handleNeighborhoodClick = (rec) => {
    setSelectedNta(rec.ntaname)
    setSelectedDetail(rec)
    setPopupInfo(rec.latitude && rec.longitude
      ? { lng: rec.longitude, lat: rec.latitude }
      : null
    )
    if (rec.latitude && rec.longitude && mapRef.current) {
      mapRef.current.flyTo({
        center: [rec.longitude, rec.latitude],
        zoom: 14,
        duration: 800
      })
    }
  }

  return (
    <div className="app">
      <Header
        activity={activity}
        onActivityChange={handleActivityChange}
        customInput={customInput}
        onCustomInputChange={setCustomInput}
        onCustomSubmit={handleCustomSubmit}
        customLoading={customLoading}
        isCustomMode={isCustomMode}
      />

      <div className="main">
        <Sidebar
          recommendations={enrichedRecommendations}
          loading={loading}
          activity={activity}
          isCustomMode={isCustomMode}
          customInput={customInput}
          selectedNta={selectedNta}
          userLocation={userLocation}
          distanceFilter={distanceFilter}
          onDistanceChange={setDistanceFilter}
          onNeighborhoodClick={handleNeighborhoodClick}
        />

        <MapView
          mapRef={mapRef}
          ntaGeojson={ntaGeojson}
          recommendations={enrichedRecommendations}
          selectedNta={selectedNta}
          userLocation={userLocation}
          popupInfo={popupInfo}
          selectedDetail={selectedDetail}
          loadingDetail={loadingDetail}
          onMapClick={handleMapClick}
          onPopupClose={() => {
            setPopupInfo(null)
            setSelectedNta(null)
            setSelectedDetail(null)
          }}
        />
      </div>
    </div>
  )
}