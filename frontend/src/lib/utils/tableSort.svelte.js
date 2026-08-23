/**
 * Reusable sortable-table state (Svelte 5 runes).
 *
 * Column definition:
 *   { key: string, labelKey: string, align?: 'left'|'right',
 *     accessor?: (row) => any,   // custom value extractor (defaults to row[key])
 *     numeric?: boolean }        // numeric columns sort descending on first click
 *
 * Usage:
 *   const sorter = createTableSort(COLUMNS, { initialKey: 'date', initialDir: 'desc' });
 *   let sortedRows = $derived(sorter.sorted(rawRows));
 *   // markup: <SortableTh {col} {sorter} />  /  sorter.toggle(col.key)
 */
export function createTableSort(columns, { initialKey = columns[0].key, initialDir = 'asc' } = {}) {
  let sortKey = $state(initialKey);
  let sortDir = $state(initialDir);

  function toggle(key) {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      const col = columns.find((c) => c.key === key);
      sortDir = col?.numeric ? 'desc' : 'asc';
    }
  }

  function sorted(rows) {
    const col = columns.find((c) => c.key === sortKey) || columns[0];
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.accessor ? col.accessor(a) : a[col.key];
      const bv = col.accessor ? col.accessor(b) : b[col.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir;
    });
  }

  return {
    get sortKey() {
      return sortKey;
    },
    get sortDir() {
      return sortDir;
    },
    toggle,
    sorted,
  };
}
