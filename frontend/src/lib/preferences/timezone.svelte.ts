const COMMON_ZONES = [
  'UTC',
  'Europe/London',
  'Europe/Paris',
  'Europe/Madrid',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Asia/Kolkata',
  'Australia/Sydney',
  'Pacific/Auckland',
];

let _timezone: string = $state('UTC');

export function displayTimezone(): string {
  return _timezone;
}

export function setDisplayTimezone(tz: string): void {
  _timezone = tz;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('displayTimezone', tz);
  }
}

export function initTimezone(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem('displayTimezone');
  if (saved) {
    _timezone = saved;
  } else {
    const detected = detectedTimezone();
    if (detected && detected !== 'UTC') {
      _timezone = detected;
      localStorage.setItem('displayTimezone', detected);
    }
  }
}

export function detectedTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return 'UTC';
  }
}

export function timezoneOptions(): { value: string; label: string }[] {
  const current = _timezone;
  const has = COMMON_ZONES.includes(current);
  const options = COMMON_ZONES.map(z => ({ value: z, label: z.replace(/_/g, ' ') }));
  if (!has && current) {
    options.unshift({ value: current, label: `${current} (current)` });
  }
  return options;
}

export function formatTimestamp(
  iso: string | null | undefined,
  opts?: {
    date?: boolean;
    time?: boolean;
    seconds?: boolean;
  },
): string {
  if (!iso) return '-';
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return iso;
  try {
    const fmt = new Intl.DateTimeFormat('sv-SE', {
      timeZone: _timezone,
      year: opts?.date !== false ? 'numeric' : undefined,
      month: opts?.date !== false ? '2-digit' : undefined,
      day: opts?.date !== false ? '2-digit' : undefined,
      hour: opts?.time !== false ? '2-digit' : undefined,
      minute: opts?.time !== false ? '2-digit' : undefined,
      second: opts?.seconds ? '2-digit' : undefined,
      hour12: false,
    });
    return fmt.format(dt);
  } catch {
    return iso;
  }
}
