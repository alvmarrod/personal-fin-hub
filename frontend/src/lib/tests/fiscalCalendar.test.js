import { describe, it, expect } from 'vitest';
import { cellsForYear, rangeFromDrag, majorPeriod, daysInMonth } from '$lib/utils/fiscalCalendar.js';

const japanPeriod = { id: 1, rule_key: 'japan', start_date: '2022-07-08', end_date: null };

describe('fiscalCalendar.cellsForYear', () => {
  it('colors gap months before the first period and the period after it', () => {
    const cells = cellsForYear(2022, [japanPeriod]);
    expect(cells[0].ruleset).toBeNull();
    expect(cells[5].ruleset).toBeNull();
    expect(cells[5].period).toBeNull();
    expect(cells[6].ruleset).toBe('japan');
    expect(cells[6].period).toBe(japanPeriod);
    expect(cells[7].ruleset).toBe('japan');
    expect(cells[11].ruleset).toBe('japan');
    expect(cells[7].start).toBe('2022-08-01');
    expect(cells[7].end).toBe('2022-08-31');
  });

  it('assigns a partial month to the ruleset covering the majority of its days', () => {
    const a = { id: 1, rule_key: 'spain', start_date: '2024-01-01', end_date: '2024-01-15' };
    const b = { id: 2, rule_key: 'japan', start_date: '2024-01-16', end_date: '2024-01-31' };
    const cells = cellsForYear(2024, [a, b]);
    expect(cells[0].ruleset).toBe('japan');
  });

  it('covers the full following year when the period is open-ended', () => {
    const cells = cellsForYear(2023, [japanPeriod]);
    expect(cells.every((c) => c.ruleset === 'japan')).toBe(true);
  });

  it('handles a closed-ended period', () => {
    const closed = { id: 1, rule_key: 'spain', start_date: '2023-01-01', end_date: '2023-06-30' };
    const cells = cellsForYear(2023, [closed]);
    expect(cells[0].ruleset).toBe('spain');
    expect(cells[5].ruleset).toBe('spain');
    expect(cells[6].ruleset).toBeNull();
    expect(cells[11].ruleset).toBeNull();
  });
});

describe('fiscalCalendar.majorPeriod', () => {
  it('returns null when no period overlaps the month', () => {
    expect(majorPeriod('2020-01-01', '2020-01-31', [japanPeriod])).toBeNull();
  });

  it('returns the single period when it fully covers the month', () => {
    expect(majorPeriod('2022-08-01', '2022-08-31', [japanPeriod])).toBe(japanPeriod);
  });

  it('prefers the period with more days inside the month', () => {
    const a = { id: 1, rule_key: 'spain', start_date: '2024-02-01', end_date: '2024-02-10' };
    const b = { id: 2, rule_key: 'japan', start_date: '2024-02-11', end_date: '2024-02-29' };
    expect(majorPeriod('2024-02-01', '2024-02-29', [a, b])).toBe(b);
  });
});

describe('fiscalCalendar.rangeFromDrag', () => {
  it('normalizes a reverse drag direction', () => {
    expect(rangeFromDrag(5, 2, 2024)).toEqual({ start_date: '2024-03-01', end_date: '2024-06-30' });
  });

  it('returns a single month for a click on one cell', () => {
    expect(rangeFromDrag(0, 0, 2024)).toEqual({ start_date: '2024-01-01', end_date: '2024-01-31' });
  });

  it('accounts for leap years', () => {
    expect(rangeFromDrag(1, 1, 2024)).toEqual({ start_date: '2024-02-01', end_date: '2024-02-29' });
    expect(rangeFromDrag(1, 1, 2023)).toEqual({ start_date: '2023-02-01', end_date: '2023-02-28' });
    expect(daysInMonth(2024, 1)).toBe(29);
  });
});