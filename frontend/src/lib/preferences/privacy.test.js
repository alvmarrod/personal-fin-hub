import { describe, it, expect, beforeEach } from 'vitest';
import { privacyHidden, togglePrivacy, initPrivacy } from './privacy.svelte';

describe('privacy store', () => {
  beforeEach(() => {
    while (privacyHidden()) {
      togglePrivacy();
    }
    localStorage.removeItem('privacyHidden');
  });

  it('defaults to visible', () => {
    expect(privacyHidden()).toBe(false);
  });

  it('toggles on and persists to localStorage', () => {
    togglePrivacy();
    expect(privacyHidden()).toBe(true);
    expect(localStorage.getItem('privacyHidden')).toBe('true');
  });

  it('toggles back off', () => {
    togglePrivacy();
    togglePrivacy();
    expect(privacyHidden()).toBe(false);
    expect(localStorage.getItem('privacyHidden')).toBe('false');
  });

  it('restores the saved state on init', () => {
    localStorage.setItem('privacyHidden', 'true');
    initPrivacy();
    expect(privacyHidden()).toBe(true);
  });

  it('keeps the default visible when nothing saved', () => {
    initPrivacy();
    expect(privacyHidden()).toBe(false);
  });
});