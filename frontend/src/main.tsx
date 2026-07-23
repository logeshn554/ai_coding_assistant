import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Restore saved theme immediately to prevent flash-of-wrong-theme
const savedTheme = localStorage.getItem('devpilot_theme') || 'dark';
if (savedTheme && savedTheme !== 'dark') {
  document.documentElement.setAttribute('data-theme', savedTheme);
}

let sessionToken = ""

// Global fetch interceptor
const originalFetch = window.fetch
window.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  if (url.includes('/auth/token')) {
    return originalFetch(input, init)
  }
  if (sessionToken) {
    init = init || {}
    init.headers = init.headers || {}
    if (init.headers instanceof Headers) {
      init.headers.set('X-Session-Token', sessionToken)
    } else if (Array.isArray(init.headers)) {
      init.headers.push(['X-Session-Token', sessionToken])
    } else {
      // @ts-ignore
      init.headers['X-Session-Token'] = sessionToken
    }
  }
  return originalFetch(input, init)
}

// Global WebSocket interceptor
const OriginalWebSocket = window.WebSocket
class PatchedWebSocket extends OriginalWebSocket {
  constructor(url: string | URL, protocols?: string | string[]) {
    if (sessionToken) {
      const urlObj = new URL(url.toString())
      urlObj.searchParams.set('token', sessionToken)
      url = urlObj.toString()
    }
    super(url, protocols)
  }
}
// @ts-ignore
window.WebSocket = PatchedWebSocket

// Fetch session token on startup, then mount the React application
async function initApp() {
  try {
    const res = await originalFetch('/auth/token')
    if (res.ok) {
      const data = await res.json()
      sessionToken = data.token
    }
  } catch (e) {
    console.error('Failed to fetch auth token:', e)
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

initApp()