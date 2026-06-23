import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { REFRESH_INTERVAL } from '../utils/helpers'

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000'

export default function useRecommendations(activity) {
    const [recommendations, setRecommendations] = useState([])
    const [loading, setLoading]                 = useState(true)
    const [lastUpdated, setLastUpdated]         = useState(null)
   
    const fetchRecommendations = useCallback(async (activityKey) => {
      setLoading(true)
      try {
        const res = await axios.get(`${API_URL}/recommendations`, {
          params: { activity: activityKey }
        })
        setRecommendations(Array.isArray(res.data) ? res.data : [])
        setLastUpdated(new Date())
      } catch (e) {
        console.error('Failed to fetch recommendations:', e)
      } finally {
        setLoading(false)
      }
    }, [])

    useEffect(() => {
        if (!activity) {
          setLoading(false)
          return
        }
        fetchRecommendations(activity)
        const interval = setInterval(() => fetchRecommendations(activity), REFRESH_INTERVAL)
        const handleVisibility = () => {
            if (!document.hidden) {
                fetchRecommendations(activity)
            }
        }   
        document.addEventListener('visibilitychange', handleVisibility)
        return () => {
            clearInterval(interval)
            document.removeEventListener('visibilitychange', handleVisibility)
        }   
    }, [activity, fetchRecommendations])
    
    const updateNeighborhood = (ntaname, data) => {
        setRecommendations(prev => prev.map(r => r.ntaname === ntaname ? { ...r, ...data } : r))
    }
    return { recommendations, loading, lastUpdated, updateNeighborhood }
}