import { describe, it, expect, beforeEach } from 'vitest';
import { setDisplayTimezone, initTimezone, displayTimezone } from './timezone.svelte';

describe('initTimezone', () => {
  beforeEach(() => {
    setDisplayTimezone('UTC');
    localStorage.removeItem('displayTimezone');
  });

  it('loads the saved timezone from localStorage', () => {
    localStorage.setItem('displayTimezone', 'Asia/Tokyo');
    initTimezone();
    expect(displayTimezone()).toBe('Asia/Tokyo');
  });
});
