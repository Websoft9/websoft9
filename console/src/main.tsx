import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import './index.css'
import './shared/i18n/i18n'

// When a new deployment replaces old chunk files, lazy-loaded routes
// may fail because the browser still references stale chunk URLs.
// Catch those errors and force a full reload to pick up the new assets.
function isChunkLoadError(message: string) {
  return (
    message.includes('dynamically imported module') ||
    message.includes('error loading dynamically imported module') ||
    message.includes('Failed to fetch dynamically imported module')
  )
}

window.addEventListener('unhandledrejection', (event) => {
  const message = event.reason?.message || String(event.reason || '')
  if (isChunkLoadError(message)) {
    window.location.reload()
  }
})

// Also catch the error variant (some bundlers throw instead of rejecting)
window.addEventListener('error', (event) => {
  const message = event.message || ''
  if (isChunkLoadError(message)) {
    window.location.reload()
  }
})

const root = createRoot(document.getElementById('root')!)

root.render(
  <StrictMode>
    <App />
  </StrictMode>,
)
