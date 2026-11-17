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

export function syncTimezoneFromProfile(profileTimezone: string | null | undefined): void {
  if (!profileTimezone) return;
  _timezone = profileTimezone;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('displayTimezone', profileTimezone);
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
