<script>
  import { onMount } from 'svelte';
  import { crud } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import Select from '$lib/components/Select.svelte';
  import AddScheduleModal from '$lib/components/modals/AddScheduleModal.svelte';
  import EditScheduleModal from '$lib/components/modals/EditScheduleModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { schedules as schedulesTutorial } from '$lib/tutorial/definitions/index';
  import schedulesMock from '$lib/tutorial/mocks/schedules';

  tutorialStore.registerMock('schedules', schedulesMock);

  let loading = $state(true);
  let error = $state(null);
  let schedules = $state([]);
  let entities = $state({});
  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 20;

  let addModalOpen = $state(false);
  let editSchedule = $state(null);
  let deleteSchedule = $state(null);

  let typeFilter = $state('all');
  let TYPE_FILTERS = $derived([
    { value: 'all', label: t('schedules.filterType') },
    { value: 'INCOME', label: t('schedules.filterMoneyIn') },
    { value: 'MONEY_OUT', label: t('schedules.filterMoneyOut') },
    { value: 'INVESTMENT_BUY', label: t('schedules.filterInvestmentBuy') },
    { value: 'INVESTMENT_SELL', label: t('schedules.filterInvestmentSell') },
  ]);

  let PERIODICITY_LABELS = $derived({
    'ONE_OFF': t('schedules.typeOneOff'),
    'DAILY': t('schedules.typeDaily'),
    'WEEKLY': t('schedules.typeWeekly'),
    'MONTHLY': t('schedules.typeMonthly'),
    'QUARTERLY': t('schedules.typeQuarterly'),
    'ANNUALLY': t('schedules.typeAnnually'),
    'CUSTOM': t('schedules.typeCustom'),
  });

  let TYPE_LABELS = $derived({
    'INCOME': t('schedules.filterMoneyIn'),
    'MONEY_OUT': t('schedules.filterMoneyOut'),
    'INVESTMENT_BUY': t('transactions.typeBuy'),
    'INVESTMENT_SELL': t('transactions.typeSell'),
    'TRANSFER': t('transactions.typeTransfer'),
    'TRANSFER_IN': t('transactions.typeTransferIn'),
    'TRANSFER_OUT': t('transactions.typeTransferOut'),
    'BALANCE_ADJUSTMENT': t('transactions.typeAdjustment'),
  });

  let filteredSchedules = $derived(
    schedules.filter(s => {
      return typeFilter === 'all' || s.type === typeFilter;
    })
  );

  let totalPages = $derived(Math.ceil(filteredSchedules.length / ITEMS_PER_PAGE));
  let paginatedSchedules = $derived(
    filteredSchedules.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
  );

  $effect(() => {
    typeFilter;
    currentPage = 1;
  });

  function getNextDate(schedule) {
    const now = new Date();
    const start = new Date(schedule.start_date);
    if (schedule.end_date && new Date(schedule.end_date) < now) return t('schedules.ended');
    if (start > now) return schedule.start_date;

    if (schedule.periodicity_type === 'ONE_OFF' || schedule.periodicity_type === 'CUSTOM') {
      return schedule.periodicity_type === 'ONE_OFF' ? schedule.start_date : '-';
    }

    let current = new Date(start);
    while (current <= now) {
      switch (schedule.periodicity_type) {
        case 'DAILY': current.setDate(current.getDate() + 1); break;
        case 'WEEKLY': current.setDate(current.getDate() + 7); break;
        case 'MONTHLY': current.setMonth(current.getMonth() + 1); break;
        case 'QUARTERLY': current.setMonth(current.getMonth() + 3); break;
        case 'ANNUALLY': current.setFullYear(current.getFullYear() + 1); break;
      }
    }
    if (schedule.end_date && current > new Date(schedule.end_date)) return t('schedules.ended');
    return current.toISOString().split('T')[0];
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [scheduleList, entityList] = await Promise.all([
        crud.schedules.getList(),
        crud.entities.getList(),
      ]);
      schedules = scheduleList;
      const emap = {};
      for (const e of entityList) emap[e.id] = e.name;
      entities = emap;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'schedules' });
    } finally {
      loading = false;
    }
  }

  async function confirmDelete() {
    if (!deleteSchedule) return;
    try {
      await crud.schedules.remove(deleteSchedule.id);
      deleteSchedule = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete schedule';
      deleteSchedule = null;
    }
  }

  onMount(() => {
    loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('schedules'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('schedules');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('schedules.title')}</h1>
    <ReplayButton page="schedules" />
  </div>
  <div style="display: flex; gap: var(--space-2);">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('schedules.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('schedules.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if schedules.length === 0}
  <EmptyState title={t('schedules.emptyTitle')} message={t('schedules.emptyMsg')} />
{:else}
  <div class="filter-bar">
    <div class="filter-group">
      {#each TYPE_FILTERS as f (f.value)}
        <button
          class="filter-btn"
          class:active={typeFilter === f.value}
          onclick={() => typeFilter = f.value}
        >{f.label}</button>
      {/each}
    </div>
    <div class="filter-info">
      {filteredSchedules.length} schedule{filteredSchedules.length !== 1 ? 's' : ''}
    </div>
  </div>

  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>{t('common.description')}</th>
          <th>{t('common.type')}</th>
          <th>{t('schedules.periodicity')}</th>
          <th>{t('common.entity')}</th>
          <th>{t('common.currency')}</th>
          <th class="num">{t('schedules.value')}</th>
          <th>{t('schedules.start')}</th>
          <th>{t('schedules.end')}</th>
          <th>{t('schedules.next')}</th>
          <th class="actions-th">{t('common.actions')}</th>
        </tr>
      </thead>
      <tbody>
        {#each paginatedSchedules as schedule (schedule.id)}
          <tr>
            <td class="cell-name">{schedule.description}</td>
            <td>{schedule.type ? (TYPE_LABELS[schedule.type] || schedule.type) : '-'}</td>
            <td>{PERIODICITY_LABELS[schedule.periodicity_type] || schedule.periodicity_type}</td>
            <td>{schedule.entity_id ? (entities[schedule.entity_id] || `#${schedule.entity_id}`) : '-'}</td>
            <td>{schedule.currency || '-'}</td>
            <td class="num">{schedule.total_value != null ? schedule.total_value.toLocaleString() : '-'}</td>
            <td>{schedule.start_date}</td>
            <td>{schedule.end_date || '∞'}</td>
            <td>{getNextDate(schedule)}</td>
            <td class="actions-cell">
              <button class="icon-btn" title="Edit" aria-label="Edit schedule" onclick={() => editSchedule = schedule}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button class="icon-btn icon-btn-danger" title="Delete" aria-label="Delete schedule" onclick={() => deleteSchedule = schedule}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if totalPages > 1}
    <Pagination
      totalItems={filteredSchedules.length}
      itemsPerPage={ITEMS_PER_PAGE}
      bind:currentPage={currentPage}
    />
  {/if}
{/if}

<AddScheduleModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditScheduleModal open={editSchedule !== null} schedule={editSchedule} onclose={() => editSchedule = null} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteSchedule !== null}
  onclose={() => deleteSchedule = null}
  onconfirm={confirmDelete}
  title={t('schedules.deleteTitle')}
  entityName={deleteSchedule ? deleteSchedule.description : ''}
  message={t('schedules.deleteMsg')}
/>

<TutorialOverlay definition={schedulesTutorial} page="schedules" onfinish={loadAll} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .filter-bar {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .filter-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin-left: auto;
  }

  .filter-btn {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
    cursor: pointer;
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
  }

  .filter-btn:hover {
    background: var(--color-surface-hover);
    border-color: var(--color-primary);
  }

  .filter-btn.active {
    background: var(--color-primary);
    color: var(--color-text-on-primary);
    border-color: var(--color-primary);
  }

  .table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .data-table th {
    padding: var(--space-3) var(--space-4);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
    position: sticky;
    top: 0;
  }

  .data-table th.num {
    text-align: right;
  }

  .data-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .data-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .actions-th {
    text-align: center;
    width: 80px;
  }

  .actions-cell {
    text-align: center;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .error-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    text-align: center;
  }

  .error-message {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
  }
</style>
