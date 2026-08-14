import { api } from '$lib/api/client.js';
import { logger } from '$lib/logger.js';

const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.0.0';
const POLL_INTERVAL_MS = 3_600_000;

let _backend = $state(null);
let _frontend = $state(null);
let _dismissed = $state(false);

let _interval = null;

/** @returns {{ current: string, latest: string | null, outdated: boolean, url: string | null } | null} */
export function backendUpdate() {
  return _dismissed ? null : _backend;
}

/** @returns {{ current: string, latest: string | null, outdated: boolean, url: string | null } | null} */
export function frontendUpdate() {
  return _dismissed ? null : _frontend;
}

export function dismissUpdate(): void {
  _dismissed = true;
}

async function poll(): Promise<void> {
  try {
    const resp = await api.get(`/updates?frontend_version=${APP_VERSION}`);
    if (resp?.enabled === false) {
      _backend = null;
      _frontend = null;
      return;
    }
    _backend = resp?.backend ?? null;
    _frontend = resp?.frontend ?? null;
  } catch (e) {
    logger.debug('[updates] check failed', e);
    _backend = null;
    _frontend = null;
  }
}

export function initUpdatePolling(): Promise<void> {
  if (_interval !== null) return Promise.resolve();
  _interval = setInterval(poll, POLL_INTERVAL_MS);
  return poll();
}
