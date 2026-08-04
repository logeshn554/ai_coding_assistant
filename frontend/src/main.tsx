import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'

// Restore saved theme immediately to prevent flash-of-wrong-theme
const savedTheme = localStorage.getItem('devpilot_theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);


let devpilotSessionId = localStorage.getItem('devpilot_session_id');
if (!devpilotSessionId) {
  devpilotSessionId = crypto.randomUUID();
  localStorage.setItem('devpilot_session_id', devpilotSessionId);
}

let sessionToken = ""

// Global fetch interceptor
const originalFetch = window.fetch
window.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  if (url.includes('/auth/token')) {
    return originalFetch(input, init)
  }
  init = init || {}
  init.headers = init.headers || {}
  if (sessionToken) {
    if (init.headers instanceof Headers) {
      init.headers.set('X-Session-Token', sessionToken)
    } else if (Array.isArray(init.headers)) {
      init.headers.push(['X-Session-Token', sessionToken])
    } else {
      // @ts-ignore
      init.headers['X-Session-Token'] = sessionToken
    }
  }
  const activeSessionId = localStorage.getItem('devpilot_session_id')
  if (activeSessionId) {
    if (init.headers instanceof Headers) {
      init.headers.set('X-Session-ID', activeSessionId)
    } else if (Array.isArray(init.headers)) {
      init.headers.push(['X-Session-ID', activeSessionId])
    } else {
      // @ts-ignore
      init.headers['X-Session-ID'] = activeSessionId
    }
  }
  return originalFetch(input, init)
}

// Global WebSocket interceptor — auto-injects auth token into every WebSocket URL
const OriginalWebSocket = window.WebSocket
class PatchedWebSocket extends OriginalWebSocket {
  constructor(url: string | URL, protocols?: string | string[]) {
    // Prefer the in-memory sessionToken; fall back to localStorage for reconnect retries
    const activeToken = sessionToken || localStorage.getItem('session_token') || ''
    if (activeToken) {
      try {
        const base = window.location.href.replace(/^http/, 'ws')
        const urlObj = new URL(url.toString(), base)
        urlObj.searchParams.set('token', activeToken)
        url = urlObj.toString()
      } catch (e) {
        console.error('Failed to patch WebSocket URL:', e)
      }
    }
    super(url, protocols)
  }
}
// @ts-ignore
window.WebSocket = PatchedWebSocket

async function fetchTokenWithRetry(retries = 5, delay = 1000): Promise<string> {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await originalFetch('/auth/token');
      if (res.ok) {
        const data = await res.json();
        if (data?.token) return data.token;
      }
    } catch (e) {
      console.warn(`Auth token fetch attempt ${i + 1} failed:`, e);
    }
    if (i < retries - 1) {
      await new Promise(r => setTimeout(r, delay));
    }
  }
  return '';
}

// Fetch session token on startup, then mount the React application
async function initApp() {
  try {
    sessionToken = await fetchTokenWithRetry();
    // Store in localStorage so reconnect retries and other components can read it
    if (sessionToken) {
      localStorage.setItem('session_token', sessionToken);
    }
  } catch (e) {
    console.error('Failed to fetch auth token:', e);
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ErrorBoundary title="Root Application Error">
        <App />
      </ErrorBoundary>
    </StrictMode>,
  )
}

initApp()