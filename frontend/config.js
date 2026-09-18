/**
 * Dynamic API Base URL Configuration for BIS AI Technical Assistant.
 *
 * Resolves the backend API root cleanly across production (Vercel -> Railway)
 * and local development environments.
 *
 * Precedence:
 * 1. window.__BIS_API_BASE_URL__ (runtime injection)
 * 2. window.BIS_API_BASE_URL
 * 3. window.VITE_API_BASE_URL
 * 4. PRODUCTION_BACKEND_URL (single place to configure your production Railway URL)
 * 5. Empty string '' (same-origin fallback for local unified servers)
 */

// Configure your production backend URL here in one place when deployed:
export const PRODUCTION_BACKEND_URL = '';

export function getApiBaseUrl() {
    if (typeof window !== 'undefined') {
        const rawUrl = window.__BIS_API_BASE_URL__ || 
                       window.BIS_API_BASE_URL || 
                       window.VITE_API_BASE_URL || 
                       PRODUCTION_BACKEND_URL;
        if (rawUrl) {
            return String(rawUrl).replace(/\/+$/, '');
        }

        // Local development fallback:
        // When running frontend on a separate static dev server (e.g. port 3000, 5173, etc.)
        // while the FastAPI/Uvicorn backend runs on port 8000
        const host = window.location?.hostname || '';
        const port = window.location?.port || '';
        if (host === 'localhost' || host === '127.0.0.1' || !host) {
            if (port && port !== '8000' && port !== '3000') {
                return `http://${host || '127.0.0.1'}:8000`;
            }
        }
        return '';
    }
    return PRODUCTION_BACKEND_URL || '';
}

export function apiUrl(endpoint) {
    const base = getApiBaseUrl();
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return base ? `${base}${cleanEndpoint}` : cleanEndpoint;
}

// Attach to window for non-module script access if needed
if (typeof window !== 'undefined') {
    window.getApiBaseUrl = getApiBaseUrl;
    window.apiUrl = apiUrl;
}
