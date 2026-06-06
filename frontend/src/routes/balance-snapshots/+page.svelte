<script>
  import { onMount } from 'svelte';
  import { crud } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import AddBalanceSnapshotModal from '$lib/components/modals/AddBalanceSnapshotModal.svelte';
  import EditBalanceSnapshotModal from '$lib/components/modals/EditBalanceSnapshotModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';

  let loading = $state(true);
  let error = $state(null);
  let addModalOpen = $state(false);
  let editSnapshot = $state(null);
  let deleteSnapshot = $state(null);

  let snapshots = $state([]);
  let entities = $state([]);
  let entityMap = $state({});

  let selectedEntity = $state(null);

  let currentPage = $state(1);
  const PER_PAGE = 20;

  let paginatedSnapshots = $derived(
    snapshots.slice(
      (currentPage - 1) * PER_PAGE,
      currentPage * PER_PAGE
    )
  );

  let totalPages = $derived(Math.ceil(snapshots.length / PER_PAGE));

  function parseNum(val) { const n = Number(val); return isNaN(n) ? 0 : n; }
  function formatDate(d) {
    if (!d) return '-';
    const date = new Date(d);
    return date.toLocaleDateString();
  }
  function formatDateTime(d) {
    if (!d) return '-';
    const date = new Date(d);
    return date.toLocaleString();
  }

  function selectEntity(id) {
    selectedEntity = id;
    currentPage = 1;
  }

  async function loadAll() {
    loading = true;
    error = null;
    currentPage = 1;
    try {
      const [snapshotsData, entitiesData] = await Promise.all([
        crud.balanceSnapshots.getList(),
        crud.entities.getList(),
      ]);

      entityMap = {};
      for (const e of entitiesData || []) {
        entityMap[e.id] = e.name;
      }
      entities = entitiesData || [];

      snapshots = (snapshotsData || []).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      if (selectedEntity !== null) {
        snapshots = snapshots.filter(s => s.entity_id === selectedEntity);
      }
    } catch (e) {
      error = e.message || 'Failed to load balance snapshots';
    } finally {
      loading = false;
    }
  }

  onMount(loadAll);
</script>

<div class="page-header">
  <h1 class="page-title">Balance Snapshots</h1>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>+ Add Balance</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message="Loading balance snapshots..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if snapshots.length === 0}
  <EmptyState title="No balance snapshots yet" message="Add your first balance snapshot to start tracking account balances over time." />
{:else}
  <div class="filter-bar">
    <label>
      Filter by Entity
      <select bind:value={selectedEntity} onchange={() => selectEntity(selectedEntity)}>
        <option value={null}>All Entities</option>
        {#each entities as entity}
          <option value={entity.id}>{entity.name}</option>
        {/each}
      </select>
    </label>
  </div>

  <div class="table-section">
    <div class="table-wrap">
      <table class="snapshot-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Entity</th>
            <th>Currency</th>
            <th class="num">Amount</th>
            <th>Notes</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedSnapshots as snapshot}
            <tr>
              <td>{formatDateTime(snapshot.timestamp)}</td>
              <td>{entityMap[snapshot.entity_id] || snapshot.entity_id}</td>
              <td>{snapshot.currency}</td>
              <td class="num">{parseNum(snapshot.amount).toLocaleString()}</td>
              <td class="cell-notes">{snapshot.notes || '-'}</td>
              <td>
                <button class="icon-btn" title="Edit snapshot" onclick={() => editSnapshot = snapshot}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="icon-btn icon-btn-danger" title="Delete snapshot" onclick={() => deleteSnapshot = snapshot}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if totalPages > 1}
      <Pagination
        totalItems={snapshots.length}
        itemsPerPage={PER_PAGE}
        bind:currentPage={currentPage}
      />
    {/if}
  </div>
{/if}

<AddBalanceSnapshotModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditBalanceSnapshotModal open={editSnapshot !== null} snapshot={editSnapshot} onclose={() => editSnapshot = null} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteSnapshot !== null}
  title="Delete Balance Snapshot"
  message={deleteSnapshot ? `Are you sure you want to delete this balance snapshot? The associated adjustment transaction will also be removed.` : ''}
  onconfirm={async () => {
    if (!deleteSnapshot) return;
    await api.del(`/balance-snapshots/${deleteSnapshot.id}`);
    deleteSnapshot = null;
    loadAll();
  }}
  oncancel={() => deleteSnapshot = null}
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

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .filter-bar {
    margin-bottom: var(--space-4);
  }

  .filter-bar label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .filter-bar select {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
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

  .snapshot-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .snapshot-table th {
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

  .snapshot-table th.num {
    text-align: right;
  }

  .snapshot-table th.actions-col {
    width: 80px;
    text-align: center;
  }

  .snapshot-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-muted);
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast);
    vertical-align: middle;
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
