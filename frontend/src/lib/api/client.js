const BASE = '/api/v1';

import { logger } from '$lib/logger.js';

window.__tutorialMockStore = null;
window.__seq = 0;
const seq = () => ++window.__seq;

logger.debug('[mock] BUILD v4-seq loaded');

/**
 * Enable mock responses for tutorial mode.
 * Call with null to disable.
 * @param {Record<string, any> | null} mocks
 */
export function setMockStore(mocks) {
  logger.debug(`[mock#${seq()}] setMockStore:`, mocks ? 'enabled' : 'disabled', mocks ? '' : new Error().stack?.split('\n').slice(2, 5).join(' | '));
  window.__tutorialMockStore = mocks;
}

/**
 * Base HTTP client for the Fin Hub API.
 * All requests are JSON, errors are consistently wrapped.
 */

class ApiError extends Error {
  /** @param {string} message @param {number} status @param {object} [body] */
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

let activeProfileId = null;

const PUBLIC_PREFIXES = ['/profiles', '/health', '/updates'];

/**
 * Set the active profile id attached to every request.
 * Call with null to clear (e.g. logout / picker screen).
 * @param {number | string | null} id
 */
export function setActiveProfileId(id) {
  activeProfileId = id;
}

/** @returns {{ 'Content-Type': string, 'X-Profile-ID'?: string }} */
function jsonHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (activeProfileId != null) {
    headers['X-Profile-ID'] = String(activeProfileId);
  }
  return headers;
}

/**
 * @param {string} path
 * @param {RequestInit} [opts]
 * @returns {Promise<any>}
 */
async function request(path, opts = {}) {
  const store = window.__tutorialMockStore;
  if (store) {
    const key = path.split('?')[0];
    let entry = store[key];
    if (entry === undefined) {
      for (const k of Object.keys(store)) {
        if (k.endsWith('/') && path.startsWith(k)) {
          entry = store[k];
          break;
        }
      }
    }
    if (entry !== undefined) {
      logger.debug(`[mock#${seq()}] HIT:`, key);
      return typeof entry === 'function' ? entry(path) : entry;
    }
    logger.debug(`[mock#${seq()}] MISS:`, key);
  } else {
    logger.debug(`[mock#${seq()}] no store set, using real fetch:`, path);
  }

  if (activeProfileId == null && !PUBLIC_PREFIXES.some((p) => path.startsWith(p))) {
    throw new ApiError('No active profile. Please select a profile first.', 401);
  }

  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    ...opts,
    headers: { ...jsonHeaders(), ...opts.headers },
  });

  if (!res.ok) {
    let body;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    const detail = body?.detail || res.statusText || 'Request failed';
    throw new ApiError(detail, res.status, body);
  }

  if (res.status === 204) return null;
  return res.json();
}

export { ApiError };

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
  put: (path, data) => request(path, { method: 'PUT', body: JSON.stringify(data) }),
  patch: (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data) }),
  del: (path) => request(path, { method: 'DELETE' }),
};
