import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// --- Cockpit dark theme integration ---
// Each Cockpit plugin runs in its own iframe. The shell sets localStorage
// "shell:style" and dispatches events when the user toggles light/dark.
// We must listen and toggle the PF6 dark class on our own <html>.
function setCockpitDarkMode(style) {
  const s = style || localStorage.getItem('shell:style') || 'auto';
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const dark = s === 'dark' || (s === 'auto' && prefersDark);
  document.documentElement.classList.toggle('pf-v6-theme-dark', dark);
}

window.addEventListener('storage', (event) => {
  if (event.key === 'shell:style') setCockpitDarkMode();
});

window.addEventListener('cockpit-style', (event) => {
  if (event instanceof CustomEvent) setCockpitDarkMode(event.detail?.style);
});

if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    setCockpitDarkMode();
  });
}

setCockpitDarkMode();
// --- End dark theme integration ---

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
