import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, waitFor, cleanup, within } from '@testing-library/svelte';
import FiscalCalendarStrip from '../components/FiscalCalendarStrip.svelte';
import { setLocale } from '$lib/i18n/index.svelte';

describe('FiscalCalendarStrip', () => {
  beforeEach(() => setLocale('en-US'));
  afterEach(cleanup);

  it('renders the current year fully colored by an open-ended period', () => {
    const periods = [{ id: 1, rule_key: 'japan', start_date: '2022-07-08', end_date: null }];
    const { container } = render(FiscalCalendarStrip, { props: { periods } });
    const cells = within(container).getAllByRole('gridcell');
    expect(cells).toHaveLength(12);
    const japanCells = container.querySelectorAll('.strip-cell.swatch-japan');
    expect(japanCells).toHaveLength(12);
  });

  it('marks the year before the period fully as gap and the following year colored', async () => {
    const periods = [{ id: 1, rule_key: 'japan', start_date: '2023-03-01', end_date: null }];
    const { container } = render(FiscalCalendarStrip, { props: { periods } });
    const strip = within(container);

    const back = strip.getByRole('button', { name: '‹' });
    for (let i = 0; i < 4; i++) await fireEvent.click(back);
    expect(within(container).getByText('2022')).toBeTruthy();
    expect(container.querySelectorAll('.strip-cell.gap')).toHaveLength(12);
    expect(container.querySelectorAll('.strip-cell.swatch-japan')).toHaveLength(0);

    const fwd = strip.getByRole('button', { name: '›' });
    await fireEvent.click(fwd);
    expect(within(container).getByText('2023')).toBeTruthy();
    expect(container.querySelectorAll('.strip-cell.swatch-japan').length).toBeGreaterThan(0);
  });

  it('opens the inline editor after a drag and creates a period with the selected range', async () => {
    const oncreate = vi.fn(async () => {});
    const { container } = render(FiscalCalendarStrip, { props: { periods: [], oncreate } });
    const strip = within(container);

    const cells = strip.getAllByRole('gridcell');
    await fireEvent.pointerDown(cells[0], { button: 0 });
    await fireEvent.pointerEnter(cells[1]);
    await fireEvent.pointerUp(window);

    expect(strip.getByText('Assign a rule to this range')).toBeTruthy();
    await fireEvent.click(strip.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(oncreate).toHaveBeenCalledTimes(1));
    expect(oncreate).toHaveBeenCalledWith({
      rule_key: 'default',
      start_date: '2026-01-01',
      end_date: '2026-02-28',
    });
  });

  it('edits the period under the pointer instead of creating an overlap', async () => {
    const onupdate = vi.fn(async () => {});
    const periods = [{ id: 1, rule_key: 'japan', start_date: '2026-03-01', end_date: null }];
    const { container } = render(FiscalCalendarStrip, { props: { periods, onupdate } });
    const strip = within(container);

    const cells = strip.getAllByRole('gridcell');
    await fireEvent.pointerDown(cells[3], { button: 0 });
    await fireEvent.pointerUp(window);

    expect(strip.getByText('Edit the rule for this range')).toBeTruthy();
    await fireEvent.click(strip.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onupdate).toHaveBeenCalledTimes(1));
    expect(onupdate).toHaveBeenCalledWith(1, {
      rule_key: 'japan',
      start_date: '2026-03-01',
      end_date: null,
    });
  });
});