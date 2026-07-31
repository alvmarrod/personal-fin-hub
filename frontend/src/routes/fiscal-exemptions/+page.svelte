<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { crud } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import AddFiscalExemptionModal from '$lib/components/modals/AddFiscalExemptionModal.svelte';
  import EditFiscalExemptionModal from '$lib/components/modals/EditFiscalExemptionModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { fiscalExemptions as fiscalExemptionsTutorial } from '$lib/tutorial/definitions/index';
  import fiscalExemptionsMock from '$lib/tutorial/mocks/fiscal-exemptions';

  tutorialStore.registerMock('fiscal-exemptions', fiscalExemptionsMock);

  let loading = $state(true);
  let error = $state(null);
  let exemptions = $state([]);
  let dependents = $state({});

  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingExemption = $state(null);
  let deletingExemption = $state(null);

  function hasDependents(id) {
    return dependents[id] || false;
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const list = await crud.fiscalExemptions.getList();
      exemptions = list;

      const depMap = {};
      for (const ex of list) {
        try {
          const txns = await fetch(`/api/v1/transactions?fiscal_exemption_id=${ex.id}`).then(r => r.json()).catch(() => []);
          depMap[ex.id] = txns.length > 0;
        } catch {
          depMap[ex.id] = false;
        }
      }
      dependents = depMap;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'fiscal exemptions' });
    } finally {
      loading = false;
    }
  }

  function handleEdit(exemption) {
    editingExemption = exemption;
    editModalOpen = true;
  }

  function handleDelete(exemption) {
    deletingExemption = exemption;
    deleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!deletingExemption) return;
    try {
      await crud.fiscalExemptions.remove(deletingExemption.id);
      deleteModalOpen = false;
      deletingExemption = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete fiscal exemption';
      deleteModalOpen = false;
      deletingExemption = null;
    }
  }

  onMount(async () => {
    const wasResumed = await tutorialStore.resume('fiscal-exemptions', fiscalExemptionsTutorial, fiscalExemptionsMock);
    if (!wasResumed) {
      if (tutorialStore.isActive()) {
        await tutorialStore.skip();
      }
      const shouldStart = !tutorialStore.isPageSeen('fiscal-exemptions');
      if (shouldStart) {
        await tutorialStore.start('fiscal-exemptions', fiscalExemptionsTutorial);
      }
    }

    loadAll();
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('fiscalExemptions.title')}</h1>
    <ReplayButton page="fiscal-exemptions" />
  </div>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('fiscalExemptions.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('fiscalExemptions.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if exemptions.length === 0}
  <EmptyState title={t('fiscalExemptions.emptyTitle')} message={t('fiscalExemptions.emptyMsg')} />
{:else}
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>{t('common.type')}</th>
          <th>{t('common.description')}</th>
          <th class="num">{t('common.amount')}</th>
          <th class="num">{t('fiscalExemptions.rate')}</th>
          <th class="num">{t('fiscalExemptions.rateLimit')}</th>
          <th class="actions-th">{t('common.actions')}</th>
        </tr>
      </thead>
      <tbody>
        {#each exemptions as ex (ex.id)}
          <tr>
            <td class="cell-name">{ex.exemption_type}</td>
            <td class="cell-desc">{ex.description || '-'}</td>
            <td class="num">{ex.exemption_amount?.toLocaleString() ?? '-'}</td>
            <td class="num">{ex.exemption_rate ?? 100}%</td>
            <td class="num">{ex.exemption_rate_limit != null ? ex.exemption_rate_limit.toLocaleString() : '-'}</td>
            <td class="actions-cell">
              <button class="icon-btn" title="Edit" aria-label="Edit exemption" onclick={() => handleEdit(ex)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              {#if hasDependents(ex.id)}
                <button class="icon-btn icon-btn-disabled" disabled title="Cannot delete: has linked transactions" aria-label="Cannot delete exemption">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              {:else}
                <button class="icon-btn icon-btn-danger" title="Delete" aria-label="Delete exemption" onclick={() => handleDelete(ex)}>
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
{/if}

<AddFiscalExemptionModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditFiscalExemptionModal open={editModalOpen} exemption={editingExemption} onclose={() => { editModalOpen = false; editingExemption = null; }} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingExemption = null; }}
  onconfirm={confirmDelete}
  title={t('fiscalExemptions.deleteTitle')}
  entityName={deletingExemption ? deletingExemption.exemption_type : ''}
  message={t('fiscalExemptions.deleteMsg')}
/>

<TutorialOverlay definition={fiscalExemptionsTutorial} page="fiscal-exemptions" onfinish={loadAll} />

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

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
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

  .cell-desc {
    color: var(--color-text-secondary);
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

  .icon-btn-disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .icon-btn-disabled:hover {
    background: none;
    color: var(--color-text-muted);
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
