import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';

const { healthMock } = vi.hoisted(() => ({
  healthMock: { marketApi: vi.fn(() => 'ok'), dismissOutage: vi.fn() },
}));

vi.mock('$lib/stores/health.svelte', () => ({
  marketApi: healthMock.marketApi,
  dismissOutage: healthMock.dismissOutage,
}));

const { default: HealthBadges } = await import('./HealthBadges.svelte');

describe('HealthBadges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('renders nothing while the market API is healthy', () => {
    healthMock.marketApi.mockReturnValue('ok');
    const { container } = render(HealthBadges);
    expect(container.querySelector('.health-badges')).toBeNull();
  });

  it('renders the outage banner when the market API is unavailable', () => {
    healthMock.marketApi.mockReturnValue('unavailable');
    render(HealthBadges);
    expect(screen.getByText('Market API not available')).toBeTruthy();
  });

  it('dismisses the outage banner', async () => {
    healthMock.marketApi.mockReturnValue('unavailable');
    render(HealthBadges);

    await fireEvent.click(screen.getByTitle('Dismiss'));

    expect(healthMock.dismissOutage).toHaveBeenCalled();
  });
});
