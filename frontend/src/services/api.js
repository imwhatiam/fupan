/**
 * api.js
 *
 * Centralised HTTP client for all backend API calls.
 * The base URL is injected at runtime via window.__API_BASE__
 * (set in index.html) so the same build works in both
 * development (Vite proxy) and production (nginx reverse-proxy).
 */

/** Base URL – falls back to localhost:8000 when the runtime variable is absent. */
const API_BASE = window.__API_BASE__ || 'http://localhost:8000/api';

/**
 * Thin fetch wrapper that throws on non-2xx responses.
 *
 * @param {string} path     - API path, e.g. "/fupan/?date=2026-03-03"
 * @param {object} options  - Standard fetch options (method, headers, body…)
 * @returns {Promise<any>}  - Parsed JSON response body
 */
async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  /** Initialise the page: determine which date to show and trigger async
   *  data download for today if not yet available.
   *  @returns {{ date, hint, is_today, available_dates }} */
  init: () => fetchJSON('/init/', { method: 'POST' }),

  /** List all trading dates that have data in the database (descending). */
  getAvailableDates: () => fetchJSON('/dates/'),

  /**
   * Fetch the daily review table (stocks with ≥8 % move and ≥800 M CNY volume).
   * @param {string} date - "YYYY-MM-DD"
   */
  getFupan: (date) => fetchJSON(`/fupan/?date=${date}`),

  /**
   * Fetch the industry analysis (>5 % gainers and top-10 % gainers by sector).
   * @param {string} date - "YYYY-MM-DD"
   */
  getIndustry: (date) => fetchJSON(`/industry/?date=${date}`),

  /**
   * Fetch the 100-day new high / new low analysis.
   * @param {string} date - "YYYY-MM-DD"
   */
  getHundredDay: (date) => fetchJSON(`/hundred-day/?date=${date}`),
};