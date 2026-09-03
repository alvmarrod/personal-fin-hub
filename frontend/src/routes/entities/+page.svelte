<script>
  import { onMount } from 'svelte';
  import { analytics, crud, currenciesApi } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { LoadingSpinner, EmptyState, Select } from '$lib/components/index.js';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import AddEntityModal from '$lib/components/modals/AddEntityModal.svelte';
  import EditEntityModal from '$lib/components/modals/EditEntityModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { entities as entitiesTutorial } from '$lib/tutorial/definitions/index';
  import entitiesMock from '$lib/tutorial/mocks/entities';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte';
  import { formatAmount } from '$lib/utils/format.svelte';

  tutorialStore.registerMock('entities', entitiesMock);

  let loading = $state(true);
  let error = $state(null);

  let entities = $state([]);
  let holdingsByEntity = $state([]);
  let convertedHoldings = $state([]);
  let entityDependents = $state({});
  let currencyCodes = $state([]);

  let selectedEntityId = $state(null);
  let expandedEntityId = $state(null);
  let historicalData = $state({ labels: [], values: [], investmentValues: [] });
  let historicalLoading = $state(false);

  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingEntity = $state(null);
  let deletingEntity = $state(null);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  function getCash(entityId) {
    return convertedHoldings
      .filter(h => h.entity_id === entityId && h.asset_class === 'CASH')
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function getOthers(entityId) {
    return convertedHoldings
      .filter(h => h.entity_id === entityId && h.asset_class !== 'CASH')
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function fmtMoney(value) {
    return value ? `${_currencySymbol}${formatAmount(value, _displayCurrency)}` : '-';
  }

  function getEntityCurrencies(entityId) {
    return [...new Set(
      holdingsByEntity
        .filter(h => h.entity_id === entityId && h.currency)
        .map(h => h.currency)
    )].sort();
  }

  function getEntityAssetClasses(entityId) {
    return [...new Set(
      holdingsByEntity
        .filter(h => h.entity_id === entityId && h.asset_class)
        .map(h => h.asset_class)
    )].sort();
  }

  function getNativeValue(entityId, currency, assetClass) {
    return holdingsByEntity
      .filter(h => h.entity_id === entityId && h.currency === currency && h.asset_class === assetClass)
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function fmtNative(value, currency) {
    return value ? `${getSymbolFor(currency)}${formatAmount(value, currency)}` : '-';
  }

  function hasDependents(entityId) {
    const deps = entityDependents[entityId];
    if (!deps) return false;
    return deps.has_transactions || deps.has_balance_snapshots || deps.has_schedules;
  }

  function getDependentsTooltip(entityId) {
    const deps = entityDependents[entityId];
    if (!deps) return '';
    const parts = [];
    if (deps.has_transactions) parts.push('transactions');
    if (deps.has_balance_snapshots) parts.push('balance snapshots');
    if (deps.has_schedules) parts.push('schedules');
    if (parts.length === 0) return '';
    return t('entities.cannotDeleteMsg', { deps: parts.join(', ') });
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [entityList, holdingsData, convertedData, currencyList] = await Promise.all([
        crud.entities.getList(),
        analytics.holdingsByEntity(),
        analytics.holdingsByEntity(displayCurrency()),
        currenciesApi.getList().catch(() => []),
      ]);
      entities = entityList;
      holdingsByEntity = holdingsData;
      convertedHoldings = convertedData;
      currencyCodes = currencyList || [];

      // Load dependents for all entities in parallel
      const dependentsPromises = entityList.map(e =>
        crud.entities.getDependents(e.id).catch(() => ({
          has_transactions: false,
          has_balance_snapshots: false,
          has_schedules: false,
        }))
      );
      const dependentsList = await Promise.all(dependentsPromises);
      const dependentsMap = {};
      entityList.forEach((e, i) => {
        dependentsMap[e.id] = dependentsList[i];
      });
      entityDependents = dependentsMap;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'entities' });
    } finally {
      loading = false;
    }
  }

  async function loadHistorical(entityId) {
    historicalLoading = true;
    try {
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const data = await analytics.historical(startDate, endDate, 'month', entityId, displayCurrency());
      historicalData = {
        labels: (data || []).map(d => d.period || d.date),
        values: (data || []).map(d => d.total_value),
        investmentValues: (data || []).map(d => d.investment_value ?? 0),
      };
    } catch {
      historicalData = { labels: [], values: [], investmentValues: [] };
    } finally {
      historicalLoading = false;
    }
  }

  function handleRowClick(entityId) {
    selectedEntityId = selectedEntityId === entityId ? null : entityId;
  }

  function toggleExpand(entityId) {
    if (expandedEntityId === entityId) {
      expandedEntityId = null;
      historicalData = { labels: [], values: [], investmentValues: [] };
      return;
    }
    expandedEntityId = entityId;
    selectedEntityId = entityId;
    loadHistorical(entityId);
  }

  function handleCurrencyChange(event) {
    setDisplayCurrency(event.target.value);
    loadAll();
    if (expandedEntityId) loadHistorical(expandedEntityId);
  }

  function handleEdit(entity) {
    editingEntity = entity;
    editModalOpen = true;
  }

  function handleDelete(entity) {
    deletingEntity = entity;
    deleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!deletingEntity) return;
    try {
      await crud.entities.remove(deletingEntity.id);
      deleteModalOpen = false;
      if (selectedEntityId === deletingEntity.id) {
        selectedEntityId = null;
      }
      if (expandedEntityId === deletingEntity.id) {
        expandedEntityId = null;
        historicalData = { labels: [], values: [], investmentValues: [] };
      }
      deletingEntity = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete entity';
      deleteModalOpen = false;
      deletingEntity = null;
    }
  }

  onMount(() => {
    loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('entities'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('entities');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('entities.title')}</h1>
    <ReplayButton page="entities" />
  </div>
  <div class="page-actions">
    <Select
      value={_displayCurrency}
      aria-label={t('entities.displayCurrency')}
      options={currencyCodes.map(c => ({ value: c, label: c }))}
      onchange={handleCurrencyChange}
    />
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('entities.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('entities.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if entities.length === 0}
  <EmptyState title={t('entities.emptyTitle')} message={t('entities.emptyMsg')} />
{:else}
  <div class="table-section">
    <div class="table-wrap">
      <table class="entity-table">
        <thead>
          <tr>
            <th>{t('common.name')}</th>
            <th>{t('common.type')}</th>
            <th>{t('entities.country')}</th>
            <th class="num">{t('entities.class.cash')}</th>
            <th class="num">{t('entities.class.others')}</th>
            <th class="actions-th">{t('common.actions')}</th>
          </tr>
        </thead>
          <tbody>
            {#each entities as entity (entity.id)}
              <tr
                class:selected={selectedEntityId === entity.id}
                onclick={() => handleRowClick(entity.id)}
                role="button"
                tabindex="0"
                onkeypress={(e) => e.key === 'Enter' && handleRowClick(entity.id)}
              >
                <td class="cell-name">
                  <span class="cell-name-inner">
                    {#if getEntityCurrencies(entity.id).length}
                      <button
                        class="expand-btn"
                        aria-label={t('entities.toggleHoldings')}
                        aria-expanded={expandedEntityId === entity.id}
                        onclick={(e) => { e.stopPropagation(); toggleExpand(entity.id); }}
                      >
                        <span class="expand-icon">{expandedEntityId === entity.id ? '▼' : '▶'}</span>
                      </button>
                    {/if}
                    {entity.name}
                    {#if hasDependents(entity.id)}
                      <span class="dependents-indicator" title={getDependentsTooltip(entity.id)}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                          <line x1="12" y1="9" x2="12" y2="13"></line>
                          <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                      </span>
                    {/if}
                  </span>
                </td>
                <td>{entity.entity_type}</td>
                <td>{entity.country || '-'}</td>
                <td class="num">{fmtMoney(getCash(entity.id))}</td>
                <td class="num">{fmtMoney(getOthers(entity.id))}</td>
                <td class="actions-cell">
                  <button class="icon-btn" title={t('common.edit')} aria-label={t('entities.editAria')} onclick={(e) => { e.stopPropagation(); handleEdit(entity); }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                  </button>
                  {#if hasDependents(entity.id)}
                    <button class="icon-btn icon-btn-disabled" disabled title={getDependentsTooltip(entity.id)} aria-label={t('entities.cannotDelete')}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  {:else}
                    <button class="icon-btn icon-btn-danger" title={t('common.delete')} aria-label={t('entities.deleteAria')} onclick={(e) => { e.stopPropagation(); handleDelete(entity); }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  {/if}
                </td>
              </tr>
              {#if expandedEntityId === entity.id}
                <tr class="items-row">
                  <td colspan="6">
                    {#if getEntityCurrencies(entity.id).length}
                      <div class="items-table-wrap">
                        <table class="items-table">
                          <thead>
                            <tr>
                              <th>{t('common.currency')}</th>
                              {#each getEntityAssetClasses(entity.id) as assetClass}
                                <th class="num">{assetClass}</th>
                              {/each}
                            </tr>
                          </thead>
                          <tbody>
                            {#each getEntityCurrencies(entity.id) as currency}
                              <tr>
                                <td>{currency}</td>
                                {#each getEntityAssetClasses(entity.id) as assetClass}
                                  <td class="num">{fmtNative(getNativeValue(entity.id, currency, assetClass), currency)}</td>
                                {/each}
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                    <div class="expansion-chart">
                      <ChartCard title={t('entities.historicalValue', { name: entity.name || 'Selected Entity' })}>
                        {#if historicalLoading}
                          <LoadingSpinner message={t('entities.loadingChart')} />
                        {:else}
                          <LineChart labels={historicalData.labels} datasets={[
                            { data: historicalData.values, label: t('dashboard.portfolioValue') },
                            { data: historicalData.investmentValues, label: t('dashboard.investmentValue') },
                          ]} />
                        {/if}
                      </ChartCard>
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
      </table>
    </div>
  </div>
{/if}

<AddEntityModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditEntityModal open={editModalOpen} onclose={() => { editModalOpen = false; editingEntity = null; }} onsuccess={loadAll} entity={editingEntity} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingEntity = null; }}
  onconfirm={confirmDelete}
  title={t('entities.deleteTitle')}
  entityName={deletingEntity?.name || ''}
/>

<TutorialOverlay definition={entitiesTutorial} page="entities" onfinish={loadAll} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .table-section {
    margin-bottom: var(--space-6);
  }

  .table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .entity-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .entity-table th {
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

  .entity-table th.num {
    text-align: right;
  }

  .entity-table th.actions-th {
    text-align: center;
    width: 80px;
  }

  .entity-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .entity-table tbody tr {
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .entity-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .entity-table tbody tr.selected {
    background: var(--color-primary-bg);
    box-shadow: inset 3px 0 0 var(--color-primary);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .cell-name-inner {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
    padding: 0;
    display: inline-flex;
    align-items: center;
  }

  .expand-icon {
    font-size: 10px;
    color: var(--color-text-muted);
    width: 12px;
    text-align: center;
  }

  .dependents-indicator {
    display: inline-flex;
    align-items: center;
    margin-left: var(--space-2);
    color: var(--color-warning);
    vertical-align: middle;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .actions-cell {
    text-align: center;
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
    background: var(--color-danger-bg);
    color: var(--color-danger);
  }

  .icon-btn-disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .icon-btn-disabled:hover {
    background: none;
    color: var(--color-text-muted);
  }

  .items-row td {
    padding: 0 !important;
    border-bottom: 1px solid var(--color-border);
  }

  .items-table-wrap {
    padding: var(--space-4) var(--space-4) 0;
    background: var(--color-surface-alt);
  }

  .items-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: var(--space-4) 0;
    font-size: var(--font-size-xs);
  }

  .items-table th,
  .items-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .items-table th {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
  }

  .items-table th.num,
  .items-table td.num {
    text-align: right;
  }

  .expansion-chart {
    padding: var(--space-4);
    background: var(--color-surface-alt);
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