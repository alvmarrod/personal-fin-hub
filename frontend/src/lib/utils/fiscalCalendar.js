const pad = (n) => String(n).padStart(2, '0');

const iso = (year, month, day) => `${year}-${pad(month + 1)}-${pad(day)}`;

export function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

export function dayNum(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / 86400000;
}

export function majorPeriod(monthStart, monthEnd, periods) {
  const start = dayNum(monthStart);
  const end = dayNum(monthEnd);
  let best = null;
  let bestDays = 0;
  for (const p of periods) {
    const ps = dayNum(p.start_date);
    const pe = p.end_date ? dayNum(p.end_date) : Number.MAX_SAFE_INTEGER;
    const from = Math.max(start, ps);
    const to = Math.min(end, pe);
    if (from > to) continue;
    const days = to - from + 1;
    if (days > bestDays) {
      best = p;
      bestDays = days;
    }
  }
  return best;
}

export function cellsForYear(year, periods) {
  const cells = [];
  for (let m = 0; m < 12; m++) {
    const start = iso(year, m, 1);
    const end = iso(year, m, daysInMonth(year, m));
    const period = majorPeriod(start, end, periods);
    cells.push({ year, month: m, start, end, ruleset: period ? period.rule_key : null, period: period || null });
  }
  return cells;
}

export function rangeFromDrag(first, last, year) {
  const a = Math.min(first, last);
  const b = Math.max(first, last);
  return { start_date: iso(year, a, 1), end_date: iso(year, b, daysInMonth(year, b)) };
}