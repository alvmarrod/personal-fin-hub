import { describe, it, expect, beforeEach } from 'vitest';
import * as store from './TutorialStore.svelte.ts';

const NAV_DEF = [
  { element: '.a', title: 't.step1.title', body: 't.step1.body' },
  { element: '.b', title: 't.step2.title', body: 't.step2.body' },
  { element: '.c', title: 't.step3.title', body: 't.step3.body', action: 'navigate', target_page: 'next' },
];

describe('TutorialStore lifecycle', () => {
  beforeEach(() => {
    localStorage.clear();
    store.abandon();
    store.setEnabled(true);
    store.init();
  });

  it('marks the page seen when a tutorial starts', () => {
    store.start('dashboard', NAV_DEF);
    expect(store.isPageSeen('dashboard')).toBe(true);
    const saved = JSON.parse(localStorage.getItem('tutorial_seen'));
    expect(saved).toContain('dashboard');
  });

  it('sets the cross-page target from the final navigate step', () => {
    store.start('dashboard', NAV_DEF);
    expect(store.getCrossPageTarget()).toBe('next');
    expect(store.getTotalSteps()).toBe(NAV_DEF.length);
  });

  it('resume switches to the target page and marks it seen', () => {
    store.start('dashboard', NAV_DEF);
    expect(store.isActive()).toBe(true);
    const resumed = store.resume('next', NAV_DEF);
    expect(resumed).toBe(true);
    expect(store.getCurrentPage()).toBe('next');
    expect(store.isPageSeen('next')).toBe(true);
    expect(store.isPageSeen('dashboard')).toBe(true);
  });

  it('handing off to a chained target keeps the tutorial active', () => {
    store.start('dashboard', NAV_DEF);
    store.resume('next', NAV_DEF);
    expect(store.isActive()).toBe(true);
    expect(store.getCrossPageTarget()).toBe('next');
  });

  it('finish on a chained page keeps the tutorial active for the handoff', () => {
    store.start('dashboard', NAV_DEF);
    store.finish();
    expect(store.isActive()).toBe(true);
    expect(store.getCrossPageTarget()).toBe('next');
    expect(store.isPageSeen('dashboard')).toBe(true);
  });

  it('finish on a non-chained tutorial tears down and marks seen', () => {
    store.start('terminal', [
      { element: '.a', title: 't.step1.title', body: 't.step1.body' },
    ]);
    store.finish();
    expect(store.isActive()).toBe(false);
    expect(store.isPageSeen('terminal')).toBe(true);
  });

  it('abandon tears down cleanly and leaves the page seen', () => {
    store.start('dashboard', NAV_DEF);
    store.abandon();
    expect(store.isActive()).toBe(false);
    expect(store.getCurrentPage()).toBe('');
    expect(store.getCrossPageTarget()).toBe('');
    expect(store.isPageSeen('dashboard')).toBe(true);
  });

  it('skip marks the page seen via force-finish', () => {
    store.start('dashboard', NAV_DEF);
    store.skip();
    expect(store.isActive()).toBe(false);
    expect(store.isPageSeen('dashboard')).toBe(true);
  });

  it('maybeStart returns false in test mode and does not start', () => {
    expect(store.maybeStart('fresh', NAV_DEF)).toBe(false);
    expect(store.isActive()).toBe(false);
    expect(store.isPageSeen('fresh')).toBe(false);
  });

  it('disabled tutorials are treated as seen', () => {
    store.setEnabled(false);
    expect(store.isEnabled()).toBe(false);
    expect(store.isPageSeen('any')).toBe(true);
    expect(localStorage.getItem('tutorial_disabled')).toBe('1');
  });
});
