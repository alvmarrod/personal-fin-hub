/**
 * UTC ⇄ profile-timezone helpers.
 *
 * Contract (`doc/timezone_model.md`): the API speaks UTC instants and the UI
 * shows and collects them in the profile timezone. A `YYYY-MM-DDTHH:MM[:SS]`
 * string without an offset comes from the API and is UTC; a `YYYY-MM-DD`
 * string is a timezone-free calendar date.
 */

const HAS_OFFSET = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/;

/** Tag a naive API timestamp as UTC so `new Date()` cannot read it as local. */
export function parseUtc(value) {
  if (typeof value !== 'string' || !DATE_TIME.test(value) || HAS_OFFSET.test(value)) return value;
  return `${value}Z`;
}

function zoneParts(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? '';
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')) % 24,
    minute: Number(get('minute')),
    second: Number(get('second')),
  };
}

function offsetMs(date, timeZone) {
  const p = zoneParts(date, timeZone);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return asUtc - Math.floor(date.getTime() / 1000) * 1000;
}

const pad = (n) => String(n).padStart(2, '0');

/** `YYYY-MM-DDTHH:mm` wall clock of an instant in the zone (for datetime-local). */
export function toZonedInput(value, timeZone) {
  const p = zoneParts(new Date(parseUtc(value)), timeZone);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`;
}

/** `YYYY-MM-DD` calendar date of an instant in the zone (for date inputs). */
export function toZonedDateInput(value, timeZone) {
  return toZonedInput(value, timeZone).slice(0, 10);
}

/**
 * Interpret a `datetime-local` value as wall clock in the zone and return the
 * UTC instant. Two passes settle the offset across a DST change.
 */
export function fromZonedInput(value, timeZone) {
  const [datePart, timePart = '00:00'] = String(value).split('T');
  const [y, mo, d] = datePart.split('-').map(Number);
  const [h, mi] = timePart.split(':').map(Number);
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  const first = wall - offsetMs(new Date(wall), timeZone);
  const utc = wall - offsetMs(new Date(first), timeZone);
  return new Date(utc);
}

/** `Europe/Madrid · GMT+1` — the offset in force at `at`. */
export function zoneLabel(timeZone, at = new Date()) {
  const name = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'shortOffset' })
    .formatToParts(at)
    .find((p) => p.type === 'timeZoneName')?.value;
  return name ? `${timeZone} · ${name}` : timeZone;
}

/** Today's calendar date in the zone. */
export function todayInZone(timeZone, now = new Date()) {
  return toZonedDateInput(now, timeZone);
}

/**
 * Advance a `YYYY-MM-DD` calendar date by one period. Pure calendar math: no
 * zone involved, so DST cannot move the result by a day.
 */
export function addPeriod(isoDate, periodicity) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  switch (periodicity) {
    case 'DAILY':
      dt.setUTCDate(dt.getUTCDate() + 1);
      break;
    case 'WEEKLY':
      dt.setUTCDate(dt.getUTCDate() + 7);
      break;
    case 'MONTHLY':
      dt.setUTCMonth(dt.getUTCMonth() + 1);
      break;
    case 'QUARTERLY':
      dt.setUTCMonth(dt.getUTCMonth() + 3);
      break;
    case 'ANNUALLY':
      dt.setUTCFullYear(dt.getUTCFullYear() + 1);
      break;
  }
  return dt.toISOString().slice(0, 10);
}
