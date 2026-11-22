import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { page } from '$app/stores';
import { setLocale } from '$lib/i18n/index.svelte';
import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
import Sidebar from '../components/Sidebar.svelte';

vi.mock('$app/stores', async () => {
  const { writable } = await import('svelte/store');
  return { page: writable({ url: new URL('http://localhost/') }) };
});

vi.mock('$lib/api/client.js', () => ({
  api: { get: vi.fn(() => Promise.resolve({ version: '0.41.0' })) },
}));

function setPath(path) {
  page.set({ url: new URL(`http://localhost${path}`) });
}

describe('Sidebar groups', () => {
  beforeEach(() => {
    localStorage.clear();
    tutorialStore.abandon();
    setLocale('en-US');
    setPath('/');
  });

  afterEach(cleanup);

  it('collapses every group by default on the dashboard', () => {
    render(Sidebar);

    expect(screen.getByRole('button', { name: 'Activity' }).getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('link', { name: 'Transactions' })).toBeNull();
    expect(screen.getByText('Dashboard')).toBeTruthy();
  });

  it('toggles a group and records the state', async () => {
    render(Sidebar);

    await fireEvent.click(screen.getByRole('button', { name: 'Activity' }));
    expect(screen.getByRole('link', { name: 'Transactions' })).toBeTruthy();
    expect(JSON.parse(localStorage.getItem('sidebar_collapsed_v1') ?? '[]')).not.toContain('activity');

    await fireEvent.click(screen.getByRole('button', { name: 'Activity' }));
    expect(screen.queryByRole('link', { name: 'Transactions' })).toBeNull();
    expect(JSON.parse(localStorage.getItem('sidebar_collapsed_v1') ?? '[]')).toContain('activity');
  });

  it('opens the group of the current page', () => {
    setPath('/debt');
    render(Sidebar);

    expect(screen.getByRole('link', { name: 'Income' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Debt' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Transactions' })).toBeNull();
  });

  it('respects a stored collapsed state', () => {
    localStorage.setItem('sidebar_collapsed_v1', JSON.stringify(['activity']));
    render(Sidebar);

    expect(screen.queryByRole('link', { name: 'Transactions' })).toBeNull();
  });

  it('opens only the tutorial target group', () => {
    tutorialStore.start('test');
    tutorialStore.setSidebarTarget('/transactions');
    render(Sidebar);

    expect(screen.getByRole('link', { name: 'Transactions' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Income' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Activity' }).getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('button', { name: 'Tracking' }).getAttribute('aria-expanded')).toBe('false');
  });
});
