/**
 * api.js — Centralised API service layer for the MRS React frontend.
 *
 * All axios calls go through this module so that:
 * - Auth tokens are injected from localStorage automatically
 * - Token refresh is attempted once on 401 before failing
 * - Base URL is read from the Vite env var VITE_BACKEND_URL
 */

import axios from 'axios';

const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

// ── Axios instance ─────────────────────────────────────────────────────────────
const api = axios.create({ baseURL: BASE });

// Inject access token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401: try refresh once, then force logout
let _refreshing = false;
let _refreshQueue = [];

const processQueue = (error, token = null) => {
  _refreshQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)));
  _refreshQueue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      if (_refreshing) {
        return new Promise((resolve, reject) => {
          _refreshQueue.push({ resolve, reject });
        })
          .then((token) => {
            original.headers.Authorization = `Bearer ${token}`;
            return api(original);
          })
          .catch((e) => Promise.reject(e));
      }
      original._retry = true;
      _refreshing = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');
        const { data } = await axios.post(`${BASE}/api/refresh`, { refresh_token: refreshToken });
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.dispatchEvent(new Event('auth:logout'));
        return Promise.reject(refreshError);
      } finally {
        _refreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// ── Unauthenticated instance for public endpoints ────────────────────────────
// Using the authenticated `api` instance for /api/recommend was causing 401s
// when the stored token was expired, which the browser misreported as a CORS
// error because FastAPI does not attach CORS headers to error responses.
const publicApi = axios.create({ baseURL: BASE });

// ── Auth ───────────────────────────────────────────────────────────────────────
export const login = (username, password) => {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);
  return api.post('/token', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
};

export const register = (username, password) =>
  api.post('/api/register', { username, password });

// ── Recommendations (public — no auth required) ───────────────────────────────
export const getRecommendations = (payload) =>
  publicApi.post('/api/recommend', payload);

// ── Interactions (JWT-protected) ───────────────────────────────────────────────
export const rateTitle = (tmdbId, interactionType) =>
  api.post('/api/rate', { tmdb_id: tmdbId, interaction_type: interactionType });

export const getWatchlist = (userId) =>
  api.get('/api/watchlist', { params: { user_id: userId } });

export default api;
