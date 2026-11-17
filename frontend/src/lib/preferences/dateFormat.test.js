import { describe, it, expect, beforeEach } from 'vitest';
import { dateFormat, setDateFormat, initDateFormat } from './dateFormat.svelte';

describe('dateFormat preference', () => {
  beforeEach(() => {
    setDateFormat('dmy');
    localStorage.removeItem('dateFormat');
  });

  it('defaults to day/month/year', () => {
    expect(dateFormat()).toBe('dmy');
  });

  it('persists the selected format', () => {
    setDateFormat('iso');
    expect(dateFormat()).toBe('iso');
    expect(localStorage.getItem('dateFormat')).toBe('iso');
  });

  it('loads the saved format on startup', () => {
    localStorage.setItem('dateFormat', 'mdy');
    initDateFormat();
    expect(dateFormat()).toBe('mdy');
  });

  it('ignores an unknown stored value', () => {
    localStorage.setItem('dateFormat', 'ymd-ish');
    initDateFormat();
    expect(dateFormat()).toBe('dmy');
  });

  it('ignores an unknown value passed to the setter', () => {
    setDateFormat('nope');
    expect(dateFormat()).toBe('dmy');
  });
});
