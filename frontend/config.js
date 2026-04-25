'use strict';

// ---------------------------------------------------------------------------
// Frontend runtime configuration
// ---------------------------------------------------------------------------
//
// Edit this one file when deploying the frontend separately from the Django
// backend. No build step, no env vars — just change the string below and
// redeploy the static files.
//
//   Same-origin deploy (default):       window.API_BASE = '';
//   Different host / port:              window.API_BASE = 'https://api.example.com';
//   Same host, API mounted at a prefix: window.API_BASE = '/backend';
//
// Trailing slash is NOT required. Leave empty when Django serves both the
// HTML shells and the API (the default `./start.sh` / PM2 setup).
// ---------------------------------------------------------------------------

window.API_BASE = '';
