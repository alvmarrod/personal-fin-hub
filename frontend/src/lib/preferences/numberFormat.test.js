import { describe, it, expect, beforeEach } from 'vitest';
import { numberFormat, setNumberFormat, initNumberFormat } from './numberFormat.svelte';

describe('numberFormat preference', () => {
  beforeEach(() => {
    setNumberFormat('dot-comma');
    localStorage.removeItem('numberFormat');
  });

  it('defaults to dot thousands and comma decimals', () => {
    expect(numberFormat()).toBe('dot-comma');
  });

  it('persists the selected format', () => {
    setNumberFormat('comma-dot');
    expect(numberFormat()).toBe('comma-dot');
    expect(localStorage.getItem('numberFormat')).toBe('comma-dot');
  });

  it('loads the saved format on startup', () => {
    localStorage.setItem('numberFormat', 'comma-dot');
    initNumberFormat();
    expect(numberFormat()).toBe('comma-dot');
  });

  it('ignores an unknown stored value', () => {
    localStorage.setItem('numberFormat', 'space-decimal');
    initNumberFormat();
    expect(numberFormat()).toBe('dot-comma');
  });

  it('ignores an unknown value passed to the setter', () => {
    setNumberFormat('nope');
    expect(numberFormat()).toBe('dot-comma');
  });
});
