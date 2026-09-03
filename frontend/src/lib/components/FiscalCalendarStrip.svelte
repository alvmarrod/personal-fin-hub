<script>
  import { t, locale } from '$lib/i18n/index.svelte';
  import { onMount } from 'svelte';
  import Select from './Select.svelte';
  import TextInput from './TextInput.svelte';
  import Button from './Button.svelte';
  import { cellsForYear, rangeFromDrag } from '$lib/utils/fiscalCalendar.js';

  let { periods = [], oncreate, onupdate } = $props();

  const rulesetOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  const now = new Date();

  const minYear = $derived(
    [...periods].reduce((y, p) => Math.min(y, Number(p.start_date.slice(0, 4))), now.getFullYear()) - 1,
  );
  const maxYear = now.getFullYear() + 1;

  let viewYear = $state(now.getFullYear());

  const cells = $derived(cellsForYear(viewYear, periods));
  const legendKeys = $derived([...new Set(periods.map((p) => p.rule_key))]);
  const monthNames = $derived(
    Array.from({ length: 12 }, (_, m) =>
      new Intl.DateTimeFormat(locale(), { month: 'short' }).format(new Date(viewYear, m, 1)),
    ),
  );

  let dragging = $state(false);
  let dragStart = $state(null);
  let dragCurrent = $state(null);
  let pointerDownCell = $state(null);

  const dragRange = $derived(
    dragging && dragStart != null && dragCurrent != null
      ? { min: Math.min(dragStart, dragCurrent), max: Math.max(dragStart, dragCurrent) }
      : null,
  );

  let editing = $state(null);
  let error = $state('');
  let saving = $state(false);

  const rangeLabel = (cell) => {
    if (!cell.ruleset) return t('fiscalRules.calendar.legendLocaleDefault');
    const end = cell.period?.end_date || t('fiscalRules.openEnded');
    return t('fiscalRules.calendar.tooltipRange', {
      ruleset: t(`fiscalRules.rule.${cell.ruleset}`),
      start: cell.period?.start_date || cell.start,
      end,
    });
  };

  function beginDrag(month, cell, e) {
    if (editing) return;
    e.preventDefault();
    dragging = true;
    dragStart = month;
    dragCurrent = month;
    pointerDownCell = cell;
  }

  function extendDrag(month) {
    if (dragging) dragCurrent = month;
  }

  function handlePointerUp() {
    if (!dragging) return;
    dragging = false;
    const start = dragStart;
    const end = dragCurrent;
    const downCell = pointerDownCell;
    dragStart = null;
    dragCurrent = null;
    pointerDownCell = null;
    if (start == null || end == null) return;
    if (downCell?.period) {
      const p = downCell.period;
      editing = { mode: 'edit', periodId: p.id, rule: p.rule_key, startDate: p.start_date, endDate: p.end_date || '' };
    } else {
      const range = rangeFromDrag(start, end, viewYear);
      editing = { mode: 'create', rule: 'default', startDate: range.start_date, endDate: range.end_date };
    }
    error = '';
  }

  function cancelDrag() {
    dragging = false;
    dragStart = null;
    dragCurrent = null;
    pointerDownCell = null;
  }

  onMount(() => {
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', cancelDrag);
    return () => {
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', cancelDrag);
    };
  });

  async function save() {
    if (!editing.startDate) {
      error = t('fiscalRules.startDateRequired');
      return;
    }
    saving = true;
    error = '';
    const payload = {
      rule_key: editing.rule,
      start_date: editing.startDate,
      end_date: editing.endDate || null,
    };
    try {
      if (editing.mode === 'edit') {
        await onupdate(editing.periodId, payload);
      } else {
        await oncreate(payload);
      }
      editing = null;
    } catch (e) {
      error = /overlap/i.test(e?.message || '')
        ? t('fiscalRules.calendar.overlap')
        : e?.message || t('modals.createFailed');
    } finally {
      saving = false;
    }
  }

  function cancelEdit() {
    editing = null;
    error = '';
  }
</script>

<div class="fiscal-strip">
  <div class="strip-head">
    <div class="legend">
      {#each legendKeys as key}
        <span class="legend-item">
          <span class="legend-dot swatch-{key}"></span>
          {t(`fiscalRules.rule.${key}`)}
        </span>
      {/each}
      <span class="legend-item">
        <span class="legend-dot swatch-gap"></span>
        {t('fiscalRules.calendar.legendLocaleDefault')}
      </span>
    </div>
    <div class="year-nav">
      <button class="nav-btn" onpointerdown={(e) => e.preventDefault()} onclick={() => viewYear = Math.max(minYear, viewYear - 1)} disabled={viewYear <= minYear}>
        ‹
      </button>
      <span class="year-label">{viewYear}</span>
      <button class="nav-btn" onpointerdown={(e) => e.preventDefault()} onclick={() => viewYear = Math.min(maxYear, viewYear + 1)} disabled={viewYear >= maxYear}>
        ›
      </button>
    </div>
  </div>

  <div class="strip" role="grid" aria-label={t('fiscalRules.title')}>
    {#each cells as cell (cell.month)}
      <button
        class="strip-cell {cell.ruleset ? `swatch-${cell.ruleset}` : 'gap'}"
        class:selected={dragRange && cell.month >= dragRange.min && cell.month <= dragRange.max}
        title={rangeLabel(cell)}
        role="gridcell"
        onpointerdown={(e) => beginDrag(cell.month, cell, e)}
        onpointerenter={() => extendDrag(cell.month)}
      >
        <span class="cell-month">{monthNames[cell.month]}</span>
      </button>
    {/each}
  </div>

  <p class="strip-hint">{t('fiscalRules.calendar.dragHint')}</p>

  {#if editing}
    <div class="strip-editor">
      <h4 class="editor-title">
        {editing.mode === 'edit' ? t('fiscalRules.calendar.editTitle') : t('fiscalRules.calendar.createTitle')}
      </h4>
      <div class="editor-fields">
        <label class="editor-field">
          <span class="editor-label">{t('fiscalRules.ruleLabel')}</span>
          <Select bind:value={editing.rule} options={rulesetOptions} />
        </label>
        <label class="editor-field">
          <span class="editor-label">{t('fiscalRules.startDate')}</span>
          <TextInput bind:value={editing.startDate} type="date" />
        </label>
        <label class="editor-field">
          <span class="editor-label">{t('fiscalRules.endDate')}</span>
          <TextInput bind:value={editing.endDate} type="date" placeholder={t('fiscalRules.openEnded')} />
        </label>
      </div>
      {#if error}
        <p class="editor-error">{error}</p>
      {/if}
      <div class="editor-actions">
        <Button variant="secondary" size="sm" onclick={cancelEdit} disabled={saving}>{t('common.cancel')}</Button>
        <Button variant="primary" size="sm" onclick={save} disabled={saving}>
          {saving ? t('common.saving') : t('common.save')}
        </Button>
      </div>
    </div>
  {/if}
</div>

<style>
  .fiscal-strip {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin: var(--space-3) 0;
  }

  .strip-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .legend {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-sm);
    background: var(--sw-tint, var(--sw, var(--color-border)));
  }

  .legend-dot.swatch-gap {
    background: transparent;
    border: 1px dashed var(--color-border-muted, var(--color-border));
  }

  .year-nav {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .nav-btn {
    width: 26px;
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-bg);
    color: var(--color-text-secondary);
    font-size: var(--font-size-base);
    cursor: pointer;
    user-select: none;
  }

  .nav-btn:hover:not(:disabled) {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .nav-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .year-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    min-width: 44px;
    text-align: center;
  }

  .strip {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: var(--space-1);
    user-select: none;
    touch-action: none;
  }

  .strip-cell {
    position: relative;
    min-height: 54px;
    padding: var(--space-1) 2px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--sw-tint, var(--color-bg));
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    cursor: pointer;
    text-align: center;
  }

  .strip-cell.gap {
    background: transparent;
    border-style: dashed;
  }

  .strip-cell.selected {
    outline: 2px solid var(--color-primary);
    outline-offset: 0;
  }

  .strip-cell:hover {
    border-color: var(--color-primary);
  }

  .cell-month {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: var(--space-1);
  }

  .strip-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  .strip-editor {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
  }

  .editor-title {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0;
  }

  .editor-fields {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: var(--space-3);
  }

  .editor-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .editor-label {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .editor-error {
    font-size: var(--font-size-sm);
    color: var(--color-danger);
    margin: 0;
  }

  .editor-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
  }

  @media (max-width: 1100px) {
    .editor-fields {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 640px) {
    .editor-fields {
      grid-template-columns: 1fr;
    }
  }

  .swatch-spain { --sw: #f97316; --sw-tint: rgba(249, 115, 22, 0.2); }
  .swatch-japan { --sw: #ef4444; --sw-tint: rgba(239, 68, 68, 0.2); }
  .swatch-default { --sw: #8b5cf6; --sw-tint: rgba(139, 92, 246, 0.2); }
  .swatch-latest { --sw: #06b6d4; --sw-tint: rgba(6, 182, 212, 0.2); }
  .swatch-none { --sw: #64748b; --sw-tint: rgba(100, 116, 139, 0.2); }
</style>