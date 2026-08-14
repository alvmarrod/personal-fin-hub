import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import UpdateBadge from './UpdateBadge.svelte';

const { backendUpdate, frontendUpdate, dismissUpdate } = vi.hoisted(() => ({
  backendUpdate: vi.fn(() => null),
  frontendUpdate: vi.fn(() => null),
  dismissUpdate: vi.fn(),
}));

vi.mock('$lib/stores/updates.svelte', () => ({
  backendUpdate,
  frontendUpdate,
  dismissUpdate,
}));

describe('UpdateBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('renders nothing when no update is available', () => {
    backendUpdate.mockReturnValue(null);
    frontendUpdate.mockReturnValue(null);
    const { container } = render(UpdateBadge);
    expect(container.querySelector('.update-badges')).toBeNull();
  });

  it('renders nothing when outdated is false', () => {
    backendUpdate.mockReturnValue({ current: '0.11.0', latest: '0.11.0', outdated: false, url: null });
    frontendUpdate.mockReturnValue(null);
    const { container } = render(UpdateBadge);
    expect(container.querySelector('.update-badges')).toBeNull();
  });

  it('renders a badge for an outdated backend', () => {
    backendUpdate.mockReturnValue({ current: '0.11.0', latest: '0.12.0', outdated: true, url: 'https://example.com/r' });
    frontendUpdate.mockReturnValue(null);
    render(UpdateBadge);
    expect(screen.getByText(/0\.12\.0/)).toBeTruthy();
  });

  it('renders a badge for an outdated frontend', () => {
    backendUpdate.mockReturnValue(null);
    frontendUpdate.mockReturnValue({ current: '0.9.0', latest: '0.9.1', outdated: true, url: 'https://example.com/f' });
    render(UpdateBadge);
    expect(screen.getByText(/0\.9\.1/)).toBeTruthy();
  });

  it('renders a badge linking to the release url', () => {
    backendUpdate.mockReturnValue({ current: '0.11.0', latest: '0.12.0', outdated: true, url: 'https://example.com/r' });
    frontendUpdate.mockReturnValue(null);
    const { container } = render(UpdateBadge);
    const link = container.querySelector('.update-badge');
    expect(link?.getAttribute('href')).toBe('https://example.com/r');
    expect(link?.getAttribute('target')).toBe('_blank');
  });

  it('dismisses on click', async () => {
    backendUpdate.mockReturnValue({ current: '0.11.0', latest: '0.12.0', outdated: true, url: 'u' });
    frontendUpdate.mockReturnValue(null);
    render(UpdateBadge);
    await fireEvent.click(screen.getByTitle('Dismiss'));
    expect(dismissUpdate).toHaveBeenCalled();
  });
});
