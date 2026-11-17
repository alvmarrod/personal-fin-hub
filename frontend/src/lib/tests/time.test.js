import { describe, it, expect } from 'vitest';
import {
  addPeriod,
  fromZonedInput,
  parseUtc,
  toZonedDateInput,
  toZonedInput,
  todayInZone,
  zoneLabel,
} from '$lib/utils/time.js';

describe('parseUtc', () => {
  it('tags a naive API timestamp as UTC', () => {
    expect(parseUtc('2026-11-17T00:30:00')).toBe('2026-11-17T00:30:00Z');
    expect(parseUtc('2026-11-17T00:30')).toBe('2026-11-17T00:30Z');
  });

  it('leaves values that already carry an offset', () => {
    expect(parseUtc('2026-11-17T00:30:00Z')).toBe('2026-11-17T00:30:00Z');
    expect(parseUtc('2026-11-17T00:30:00+02:00')).toBe('2026-11-17T00:30:00+02:00');
  });

  it('leaves calendar dates and non-strings alone', () => {
    expect(parseUtc('2026-11-17')).toBe('2026-11-17');
    expect(parseUtc(0)).toBe(0);
  });
});

describe('toZonedInput', () => {
  it('renders the wall clock of an instant in the zone', () => {
    expect(toZonedInput('2026-11-17T00:30:00Z', 'Asia/Tokyo')).toBe('2026-11-17T09:30');
    expect(toZonedInput('2026-11-17T00:30:00Z', 'America/New_York')).toBe('2026-11-16T19:30');
  });

  it('accepts a naive API timestamp', () => {
    expect(toZonedInput('2026-11-17T00:30:00', 'Asia/Tokyo')).toBe('2026-11-17T09:30');
  });

  it('renders the calendar date in the zone', () => {
    expect(toZonedDateInput('2026-11-17T00:30:00Z', 'America/New_York')).toBe('2026-11-16');
  });
});

describe('fromZonedInput', () => {
  it('round-trips through the zone', () => {
    expect(fromZonedInput('2026-11-17T09:30', 'Asia/Tokyo').toISOString()).toBe('2026-11-17T00:30:00.000Z');
    expect(toZonedInput(fromZonedInput('2026-11-17T09:30', 'Asia/Tokyo'), 'Asia/Tokyo')).toBe('2026-11-17T09:30');
  });

  it('follows the offset in force on the chosen date', () => {
    expect(fromZonedInput('2026-01-15T12:00', 'Europe/Madrid').toISOString()).toBe('2026-01-15T11:00:00.000Z');
    expect(fromZonedInput('2026-07-15T12:00', 'Europe/Madrid').toISOString()).toBe('2026-07-15T10:00:00.000Z');
  });

  it('treats a bare date as midnight in the zone', () => {
    expect(fromZonedInput('2026-01-15', 'Asia/Tokyo').toISOString()).toBe('2026-01-14T15:00:00.000Z');
  });
});

describe('zoneLabel', () => {
  it('shows the zone and the offset at that date', () => {
    expect(zoneLabel('Europe/Madrid', new Date('2026-01-15T12:00:00Z'))).toBe('Europe/Madrid · GMT+1');
    expect(zoneLabel('Europe/Madrid', new Date('2026-07-15T12:00:00Z'))).toBe('Europe/Madrid · GMT+2');
  });
});

describe('todayInZone', () => {
  it('uses the calendar day of the zone, not of the browser', () => {
    const instant = new Date('2026-11-17T00:30:00Z');
    expect(todayInZone('Asia/Tokyo', instant)).toBe('2026-11-17');
    expect(todayInZone('America/New_York', instant)).toBe('2026-11-16');
  });
});

describe('addPeriod', () => {
  it('advances calendar dates without a zone', () => {
    expect(addPeriod('2026-01-15', 'DAILY')).toBe('2026-01-16');
    expect(addPeriod('2026-01-15', 'WEEKLY')).toBe('2026-01-22');
    expect(addPeriod('2026-01-15', 'MONTHLY')).toBe('2026-02-15');
    expect(addPeriod('2026-01-15', 'QUARTERLY')).toBe('2026-04-15');
    expect(addPeriod('2026-01-15', 'ANNUALLY')).toBe('2027-01-15');
  });
});
