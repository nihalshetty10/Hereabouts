export const SCORE_COLORS = {
    'Great': '#22C55E',
    'Good': '#3B82F6',
    'Fair': '#F59E0B',
    'Poor': '#EF4444',
}

export function getScoreColor(label) {
    return SCORE_COLORS[label] || '#6B7280'
}

export function haversineDistance(lat1, lon1, lat2, lon2) {
    const R = 3958.8
    const dLat = (lat2 - lat1) * Math.PI / 180
    const dLon = (lon2 - lon1) * Math.PI / 180
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2
    return R * 2* Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const PRESET_ACTIVITIES = [
    { key: 'running',   label: 'Running',    emoji: '🏃' },
    { key: 'night_out', label: 'Night Out',  emoji: '🌙' },
    { key: 'coffee',    label: 'Coffee',     emoji: '☕' },
    { key: 'biking',    label: 'Biking',     emoji: '🚲' },
    { key: 'park',      label: 'Park',       emoji: '🌳' },
    { key: 'eating',    label: 'Eating Out', emoji: '🍽️' },
    { key: 'shopping',  label: 'Shopping',   emoji: '🛍️' },
    { key: 'exploring', label: 'Exploring',  emoji: '🗺️' }
]

export const DISTANCE_OPTIONS = [
    { label: 'All',    miles: null },
    { label: '0.5mi',  miles: 0.5 },
    { label: '1mi',    miles: 1 },
    { label: '2mi',    miles: 2 },
    { label: '5mi',    miles: 5 },
    { label: '10mi',   miles: 10 }
]

export const REFRESH_INTERVAL = 2 * 60 * 60 * 1000
