<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import Button from '$lib/components/Button.svelte';
  import AddEntityModal from '$lib/components/modals/AddEntityModal.svelte';
  import EditEntityModal from '$lib/components/modals/EditEntityModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';

  let loading = $state(true);
  let error = $state(null);

  let entities = $state([]);
  let holdingsByEntity = $state([]);
  let entityDependents = $state({});

  let selectedEntityId = $state(null);
  let historicalData = $state({ labels: [], values: [] });
  let historicalLoading = $state(false);

  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingEntity = $state(null);
  let deletingEntity = $state(null);

  let allAssetClasses = $derived([...new Set(holdingsByEntity.map(h => h.asset_class).filter(Boolean))].sort());

  function getEntityValue(entityId, assetClass) {
    return holdingsByEntity
      .filter(h => h.entity_id === entityId && h.asset_class === assetClass)
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function getEntityLiquidity(entityId) {
    return holdingsByEntity
      .filter(h => h.entity_id === entityId && h.asset_class === 'CASH')
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function getEntityAssets(entityId) {
    return holdingsByEntity
      .filter(h => h.entity_id === entityId && h.asset_class !== 'CASH')
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  function getEntityTotal(entityId) {
    return holdingsByEntity
      .filter(h => h.entity_id === entityId)
      .reduce((sum, h) => sum + h.current_value, 0);
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
    return `Cannot delete: has ${parts.join(', ')}`;
  }

  let tableColumns = $derived([
    { key: 'name', label: 'Name' },
    { key: 'entity_type', label: 'Type' },
    { key: 'country', label: 'Country' },
    ...allAssetClasses.filter(ac => ac !== 'CASH').map(ac => ({
      key: ac,
      label: ac,
      align: 'right',
      render: (row) => {
        const val = getEntityValue(row.id, ac);
        return val ? val.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-';
      },
    })),
    {
      key: 'liquidity',
      label: 'Liquidity',
      align: 'right',
      render: (row) => {
        const val = getEntityLiquidity(row.id);
        return val ? val.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-';
      },
    },
    {
      key: 'assets',
      label: 'Assets',
      align: 'right',
      render: (row) => {
        const val = getEntityAssets(row.id);
        return val ? val.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-';
      },
    },
    {
      key: 'actions',
      label: '',
      align: 'center',
      render: (row) => '',
    },
  ]);

  let tableRows = $derived(
    entities.map(e => ({
      ...e,
      id: e.id,
    }))
  );

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [entityList, holdingsData] = await Promise.all([
        crud.entities.getList(),
        analytics.holdingsByEntity(),
      ]);
      entities = entityList;
      holdingsByEntity = holdingsData;
      
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
      error = e.message || 'Failed to load entities';
    } finally {
      loading = false;
    }
  }

  async function loadHistorical(entityId) {
    selectedEntityId = entityId;
    historicalLoading = true;
    try {
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const data = await analytics.historical(startDate, endDate, 'month', entityId);
      historicalData = {
        labels: (data || []).map(d => d.period || d.date),
        values: (data || []).map(d => d.total_value),
      };
    } catch {
      historicalData = { labels: [], values: [] };
    } finally {
      historicalLoading = false;
    }
  }

  function handleRowClick(row) {
    loadHistorical(row.id);
  }

  function handleEdit(row) {
    editingEntity = row;
    editModalOpen = true;
  }

  function handleDelete(row) {
    deletingEntity = row;
    deleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!deletingEntity) return;
    try {
      await crud.entities.remove(deletingEntity.id);
      deleteModalOpen = false;
      if (selectedEntityId === deletingEntity.id) {
        selectedEntityId = null;
        historicalData = { labels: [], values: [] };
      }
      deletingEntity = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete entity';
      deleteModalOpen = false;
      deletingEntity = null;
    }
  }

  onMount(loadAll);
</script>

<div class="page-header">
  <h1 class="page-title">Entities</h1>
  <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>+ Add Entity</Button>
</div>

{#if loading}
  <LoadingSpinner message="Loading entities..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if entities.length === 0}
  <EmptyState title="No entities yet" message="Add your first entity (broker, bank, etc.) to get started." />
{:else}
  <div class="table-section">
    <div class="table-wrap">
      <table class="entity-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Country</th>
            {#each allAssetClasses.filter(ac => ac !== 'CASH') as ac}
              <th class="num">{ac}</th>
            {/each}
            <th class="num">Liquidity</th>
            <th class="num">Assets</th>
            <th class="actions-th">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each entities as entity (entity.id)}
            <tr
              class:selected={selectedEntityId === entity.id}
              onclick={() => handleRowClick(entity)}
              role="button"
              tabindex="0"
              onkeypress={(e) => e.key === 'Enter' && handleRowClick(entity)}
            >
              <td class="cell-name">
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
              </td>
              <td>{entity.entity_type}</td>
              <td>{entity.country || '-'}</td>
              {#each allAssetClasses.filter(ac => ac !== 'CASH') as ac}
                <td class="num">{getEntityValue(entity.id, ac) ? getEntityValue(entity.id, ac).toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-'}</td>
              {/each}
              <td class="num">{getEntityLiquidity(entity.id) ? getEntityLiquidity(entity.id).toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-'}</td>
              <td class="num">{getEntityAssets(entity.id) ? getEntityAssets(entity.id).toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-'}</td>
              <td class="actions-cell">
                <button class="icon-btn" title="Edit" aria-label="Edit entity" onclick={(e) => { e.stopPropagation(); handleEdit(entity); }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                </button>
                {#if hasDependents(entity.id)}
                  <button class="icon-btn icon-btn-disabled" disabled title={getDependentsTooltip(entity.id)} aria-label="Cannot delete entity">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                {:else}
                  <button class="icon-btn icon-btn-danger" title="Delete" aria-label="Delete entity" onclick={(e) => { e.stopPropagation(); handleDelete(entity); }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  {#if selectedEntityId}
    <div class="chart-section">
      <ChartCard title="Historical Value — {entities.find(e => e.id === selectedEntityId)?.name || 'Selected Entity'}">
        {#if historicalLoading}
          <LoadingSpinner message="Loading chart..." />
        {:else}
          <LineChart labels={historicalData.labels} datasets={[{ data: historicalData.values, label: 'Value' }]} />
        {/if}
      </ChartCard>
    </div>
  {/if}
{/if}

<AddEntityModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditEntityModal open={editModalOpen} onclose={() => { editModalOpen = false; editingEntity = null; }} onsuccess={loadAll} entity={editingEntity} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingEntity = null; }}
  onconfirm={confirmDelete}
  title="Delete Entity"
  entityName={deletingEntity?.name || ''}
/>

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
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

  .num.total {
    font-weight: var(--font-weight-semibold);
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

  .chart-section {
    margin-bottom: var(--space-6);
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
