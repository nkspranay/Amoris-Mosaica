// API base URL — switches between local dev and production automatically
const API_BASE = import.meta.env.VITE_API_URL || ''

// In local dev: VITE_API_URL is not set → uses '' → Vite proxy handles /api and /ws
// In production: VITE_API_URL = https://amoris-mosaica.onrender.com → calls Render directly

export const API_URL = API_BASE

export function apiUrl(path) {
  return `${API_BASE}${path}`
}

export function wsUrl(path) {
  if (API_BASE) {
    // Production — use wss:// with Render URL
    return `${API_BASE.replace('https://', 'wss://').replace('http://', 'ws://')}${path}`
  }
  // Local dev — use current host with ws://
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}