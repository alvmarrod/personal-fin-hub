import { api } from '$lib/api/client.js';

let _marketApi: 'ok' | 'unavailable' | 'unknown' = $state('unknown');
let _circuit: string = $state('unknown');
let _marketDataLastUpdated: string | null = $state(null);
let _lastChecked: string | null = $state(null);
let _dismissed: boolean = $state(false);

let _interval: ReturnType<typeof setInterval> | null = null;
let _consecutiveFailures: number = 0;

export function marketApi(): 'ok' | 'unavailable' | 'unknown' {
  return _dismissed ? 'ok' : _marketApi;
}

export function circuit(): string {
  return _circuit;
}

export function marketDataLastUpdated(): string | null {
  return _marketDataLastUpdated;
}

export function lastChecked(): string | null {
  return _lastChecked;
}

export function dismissOutage(): void {
  _dismissed = true;
}

async function poll(): Promise<void> {
  try {
    const resp = await api.get('/health');
    const checks = resp?.checks || {};
    const apiStatus = checks.market_api === 'ok' ? 'ok' : 'unavailable';

    if (apiStatus === 'ok') {
      _consecutiveFailures = 0;
      _marketApi = 'ok';
    } else {
      _consecutiveFailures++;
      if (_consecutiveFailures >= 2) {
        _marketApi = 'unavailable';
      }
    }

    _circuit = checks.market_api_circuit || 'unknown';
    _marketDataLastUpdated = checks.market_data_last_updated ?? null;
    _lastChecked = new Date().toISOString();
  } catch {
    _marketApi = 'unknown';
    _lastChecked = new Date().toISOString();
  }
}

export function initHealthPolling(): void {
  if (_interval !== null) return;
  poll();
  _interval = setInterval(poll, 60_000);
}
