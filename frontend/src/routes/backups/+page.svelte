<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { api } from '$lib/api/client.js';
  import { formatAmount, formatDateTime } from '$lib/utils/format.svelte';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Card from '$lib/components/Card.svelte';
  import CreateBackupModal from '$lib/components/modals/CreateBackupModal.svelte';
  import RestoreBackupModal from '$lib/components/modals/RestoreBackupModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { backups as backupsTutorial } from '$lib/tutorial/definitions/index';
  import backupsMock from '$lib/tutorial/mocks/backups';

  tutorialStore.registerMock('backups', backupsMock);

  const KIND_KEYS = {
    manual: 'backups.kindManual',
    daily: 'backups.kindDaily',
    'daily-catchup': 'backups.kindCatchup',
    'pre-migration': 'backups.kindPreMigration',
    'post-migration': 'backups.kindPostMigration',
    'pre-restore': 'backups.kindPreRestore',
  };

  let loading = $state(true);
  let error = $state(null);
  let actionError = $state('');
  let notice = $state('');
  let policy = $state(null);
  let items = $state([]);
  let creating = $state(false);

  let createModalOpen = $state(false);
  let createTargets = $state([]);
  let restoreOpen = $state(false);
  let restoreSource = $state(null);

  async function load() {
    loading = true;
    error = null;
    try {
      const data = await api.get('/backups');
      policy = data.policy;
      items = data.items ?? [];
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: t('backups.title') });
    } finally {
      loading = false;
    }
  }

  onMount(load);

  function kindLabel(item) {
    if (!item.tag || !KIND_KEYS[item.tag]) return t('backups.kindAutomatic');
    return t(KIND_KEYS[item.tag]);
  }

  function kindTone(item) {
    return item.tag === 'manual' ? 'manual' : 'auto';
  }

  function sizeLabel(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${formatAmount(bytes / 1024)} KB`;
    return `${formatAmount(bytes / (1024 * 1024))} MB`;
  }

  function downloadUrl(item) {
    return `/api/v1/backups/${encodeURIComponent(item.name)}`;
  }

  function doomedByRetention() {
    if (!policy || policy.retention <= 0) return [];
    if (items.length < policy.retention) return [];
    return items.slice(policy.retention - 1);
  }

  async function createNow() {
    creating = true;
    actionError = '';
    notice = '';
    try {
      const result = await api.post('/backups', {});
      notice = t('backups.created', { name: result.created.name });
      createModalOpen = false;
      await load();
    } finally {
      creating = false;
    }
  }

  async function handleCreate() {
    const doomed = doomedByRetention();
    if (doomed.length > 0) {
      createTargets = doomed;
      createModalOpen = true;
      return;
    }
    try {
      await createNow();
    } catch (e) {
      actionError = e.message || t('backups.createFailed');
    }
  }

  function openRestore(item = null) {
    restoreSource = item ? { type: 'existing', name: item.name } : { type: 'file' };
    restoreOpen = true;
  }
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('backups.title')}</h1>
    <ReplayButton page="backups" />
  </div>
  <div class="page-actions backups-actions">
    <span class="backups-import">
      <Button variant="secondary" size="sm" onclick={() => openRestore()}>{t('backups.import')}</Button>
    </span>
    <span class="backups-create">
      <Button variant="primary" size="sm" onclick={handleCreate} disabled={creating}>
        {creating ? t('backups.creating') : t('backups.createNow')}
      </Button>
    </span>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('backups.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={load}>{t('common.retry')}</Button>
  </div>
{:else}
  {#if notice}
    <p class="notice">{notice}</p>
  {/if}
  {#if actionError}
    <p class="notice notice-error">{actionError}</p>
  {/if}

  {#if policy}
  <div class="backups-top">
    <Card class="backups-policy">
      <h2 class="policy-title">{t('backups.policyTitle')}</h2>
      <p class="policy-status" class:disabled={!policy.enabled}>
        {policy.enabled ? t('backups.policyEnabled') : t('backups.policyDisabled')}
      </p>
      <dl class="policy-grid">
        <dt>{t('backups.policyScheduleLabel')}</dt>
        <dd>{t('backups.policySchedule', { time: policy.cron, timezone: policy.timezone })}</dd>
        <dt>{t('backups.policyRetentionLabel')}</dt>
        <dd>{t('backups.policyRetention', { count: policy.retention })}</dd>
        <dt>{t('backups.policyNextLabel')}</dt>
        <dd>
          {policy.next_run_at
            ? formatDateTime(policy.next_run_at)
            : t('backups.policyNextUnknown')}
        </dd>
      </dl>
      <p class="policy-note">{t('backups.policyLocal')}</p>
    </Card>
    <Card class="backups-info">
      <h2 class="policy-title">{t('backups.infoTitle')}</h2>
      <p class="info-body">{t('backups.infoBody')}</p>
      <ul class="info-list">
        <li>{t('backups.infoFormat')}</li>
        <li>{t('backups.infoContents')}</li>
        <li>{t('backups.infoExport')}</li>
      </ul>
    </Card>
  </div>
  {/if}

  {#if items.length === 0}
    <EmptyState title={t('backups.emptyTitle')} message={t('backups.emptyMsg')} />
  {:else}
    <div class="table-wrap backups-list">
      <table class="data-table">
        <thead>
          <tr>
            <th>{t('backups.colName')}</th>
            <th>{t('backups.colCreated')}</th>
            <th>{t('backups.colKind')}</th>
            <th class="num">{t('backups.colSize')}</th>
            <th class="actions-th">{t('common.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {#each items as item (item.name)}
            <tr>
              <td class="file-name" title={item.name}>
                {item.name}
                {#if item.latest}
                  <span class="latest">{t('backups.latest')}</span>
                {/if}
              </td>
              <td>{formatDateTime(item.created_at)}</td>
              <td>
                <span class="kind kind-{kindTone(item)}">{kindLabel(item)}</span>
                {#if item.app_version}
                  <span class="version">v{item.app_version}</span>
                {/if}
              </td>
              <td class="num">{sizeLabel(item.size)}</td>
              <td class="actions-cell">
                <a class="download-link backups-download" href={downloadUrl(item)} download={item.name}>
                  {t('backups.download')}
                </a>
                <button class="restore-link" onclick={() => openRestore(item)}>{t('backups.restore')}</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}

<CreateBackupModal
  open={createModalOpen}
  onclose={() => (createModalOpen = false)}
  onconfirm={createNow}
  targets={createTargets}
/>

<RestoreBackupModal
  open={restoreOpen}
  onclose={() => (restoreOpen = false)}
  source={restoreSource}
/>

<TutorialOverlay definition={backupsTutorial} page="backups" onfinish={load} />

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

  .notice {
    margin: 0 0 var(--space-4);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    background: var(--color-success-bg);
    color: var(--color-success);
    font-size: var(--font-size-sm);
  }

  .notice-error {
    background: var(--color-danger-bg);
    color: var(--color-danger);
  }

  .backups-top {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-5);
    margin-bottom: var(--space-5);
    align-items: stretch;
  }

  @media (max-width: 900px) {
    .backups-top {
      grid-template-columns: 1fr;
    }
  }

  .info-body {
    margin: 0 0 var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    line-height: 1.5;
  }

  .info-list {
    margin: 0;
    padding-left: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  .policy-title {
    font-size: var(--font-size-base);
    margin: 0 0 var(--space-2);
  }

  .policy-status {
    margin: 0 0 var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-success);
  }

  .policy-status.disabled {
    color: var(--color-text-muted);
  }

  .policy-grid {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-4);
    margin: 0;
    font-size: var(--font-size-sm);
  }

  .policy-grid dt {
    color: var(--color-text-muted);
  }

  .policy-grid dd {
    margin: 0;
    color: var(--color-text-primary);
  }

  .policy-note {
    margin: var(--space-3) 0 0;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
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

  .file-name {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .latest {
    margin-left: var(--space-2);
    padding: 0 var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--color-primary-bg);
    color: var(--color-primary);
    font-family: var(--font-family);
    font-size: var(--font-size-xs);
  }

  .kind {
    padding: 1px var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
  }

  .kind-auto {
    background: var(--color-info-bg);
    color: var(--color-info);
  }

  .kind-manual {
    background: var(--color-success-bg);
    color: var(--color-success);
  }

  .version {
    margin-left: var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .actions-th {
    text-align: right;
    width: 140px;
  }

  .actions-cell {
    text-align: right;
  }

  .download-link,
  .restore-link {
    background: none;
    border: none;
    padding: 0;
    margin-left: var(--space-3);
    font-size: var(--font-size-xs);
    font-family: inherit;
    cursor: pointer;
    color: var(--color-primary);
    text-decoration: none;
  }

  .download-link:hover,
  .restore-link:hover {
    text-decoration: underline;
  }

  .restore-link {
    color: var(--color-danger);
  }

  .error-card {
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .error-message {
    margin: 0;
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }
</style>
