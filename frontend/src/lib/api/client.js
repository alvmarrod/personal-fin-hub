const BASE = '/api/v1';

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

/** @returns {{ 'Content-Type': string }} */
function jsonHeaders() {
  return { 'Content-Type': 'application/json' };
}

/**
 * @param {string} path
 * @param {RequestInit} [opts]
 * @returns {Promise<any>}
 */
async function request(path, opts = {}) {
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
  del: (path) => request(path, { method: 'DELETE' }),
};
