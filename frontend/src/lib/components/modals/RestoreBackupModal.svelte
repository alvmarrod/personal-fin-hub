<script>
  import { t } from '$lib/i18n/index.svelte';
  import { api } from '$lib/api/client.js';
  import { formatDateTime } from '$lib/utils/format.svelte';
  import { logout } from '$lib/stores/profile.svelte.js';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';

  let { open = false, onclose, source = null } = $props();

  let step = $state('select');
  let file = $state(null);
  let details = $state(null);
  let busy = $state([]);
  let error = $state('');
  let typed = $state('');

  let isExisting = $derived(source?.type === 'existing');
  let confirmWord = $derived(t('backups.restoreWord'));
  let matches = $derived(typed === confirmWord);
  let migrations = $derived(details?.migrations ?? []);
  let closable = $derived(step !== 'migrations' && step !== 'restoring' && step !== 'done');

  $effect(() => {
    if (!open) return;
    step = 'select';
    file = null;
    busy = [];
    error = '';
    typed = '';
    if (source?.type === 'existing') {
      loadExisting();
    } else {
      details = null;
    }
  });

  $effect(() => {
    if (!open || step !== 'waiting') return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await api.get('/backups/activity');
        if (!cancelled) busy = res.busy ?? [];
      } catch {
        // The restore window blocks most routes; a failed poll is harmless.
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  });

  function messageOf(e, fallback) {
    return e?.message || fallback;
  }

  async function loadExisting() {
    step = 'checking';
    error = '';
    try {
      details = await api.post(`/backups/${encodeURIComponent(source.name)}/inspect`, {});
      step = 'waiting';
    } catch (e) {
      error = messageOf(e, t('backups.inspectFailed'));
      step = 'select';
    }
  }

  async function inspectFile() {
    if (!file) return;
    step = 'checking';
    error = '';
    try {
      details = await api.postFile('/backups/inspect', file);
      step = 'waiting';
    } catch (e) {
      error = messageOf(e, t('backups.inspectFailed'));
      details = null;
      step = 'select';
    }
  }

  function onFileChange(event) {
    file = event.target.files?.[0] ?? null;
    details = null;
    error = '';
    if (file) {
      inspectFile();
    } else {
      step = 'select';
    }
  }

  function onContinue() {
    if (busy.length > 0 || !matches) return;
    if (migrations.length > 0) {
      step = 'migrations';
      return;
    }
    performRestore();
  }

  async function performRestore() {
    step = 'restoring';
    error = '';
    try {
      if (isExisting) {
        await api.post(`/backups/${encodeURIComponent(source.name)}/restore`, {});
      } else {
        await api.postFile('/backups/restore', file);
      }
      step = 'done';
      logout();
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
      if (e?.status === 409) {
        busy = e.body?.detail?.activity ?? [];
        error = t('backups.restoreBusy');
      } else {
        error = messageOf(e, t('backups.restoreFailed'));
      }
      step = 'waiting';
    }
  }
</script>

<Modal {open} {onclose} title={t('backups.restoreTitle')} size="sm" {closable}>
  <div class="restore-body">
    {#if step === 'select'}
      <p class="desc">{t('backups.restoreDesc')}</p>
      {#if isExisting}
        <p class="file-name">{source.name}</p>
      {:else}
        <input
          class="file-input"
          type="file"
          accept=".bak,.db,.sqlite"
          onchange={onFileChange}
          aria-label={t('backups.restorePickFile')}
        />
      {/if}
      {#if error}
        <FormError message={error} />
      {/if}
      <FormActions>
        <Button variant="secondary" onclick={onclose}>{t('common.cancel')}</Button>
      </FormActions>
    {:else if step === 'checking'}
      <p class="desc">{t('backups.inspecting')}</p>
    {:else if step === 'waiting'}
      <p class="desc">{t('backups.restoreWarn')}</p>
      <dl class="details">
        <dt>{t('backups.file')}</dt>
        <dd class="file-name">{details?.name ?? source?.name}</dd>
        {#if details?.created_at}
          <dt>{t('backups.created')}</dt>
          <dd>{formatDateTime(details.created_at)}</dd>
        {/if}
      </dl>
      {#if busy.length > 0}
        <div class="busy">
          <p>{t('backups.waitingFor', { count: busy.length })}</p>
          <ul>
            {#each busy as item (item.name)}
              <li>{item.name}</li>
            {/each}
          </ul>
        </div>
      {:else}
        <p class="ready">{t('backups.ready')}</p>
      {/if}
      <FormField label={t('backups.restoreTypeToConfirm', { word: confirmWord })} required>
        <TextInput bind:value={typed} placeholder={confirmWord} />
      </FormField>
      {#if error}
        <FormError message={error} />
      {/if}
      <FormActions>
        <Button variant="secondary" onclick={onclose}>{t('common.cancel')}</Button>
        <Button variant="danger" onclick={onContinue} disabled={busy.length > 0 || !matches}>
          {t('backups.restoreContinue')}
        </Button>
      </FormActions>
    {:else if step === 'migrations'}
      <p class="desc">{t('backups.migrationsMsg', { count: migrations.length })}</p>
      <ul class="migration-list">
        {#each migrations as migration (migration)}
          <li>{migration}</li>
        {/each}
      </ul>
      <p class="note">{t('backups.migrationsNote')}</p>
      <FormActions>
        <Button variant="primary" onclick={performRestore}>{t('backups.restoreContinue')}</Button>
      </FormActions>
    {:else if step === 'restoring'}
      <p class="desc">{t('backups.restoring')}</p>
    {:else if step === 'done'}
      <p class="desc">{t('backups.restoreDone')}</p>
    {/if}
  </div>
</Modal>

<style>
  .restore-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.5;
  }

  .file-name {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    margin: 0;
    word-break: break-all;
  }

  .details {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
    font-size: var(--font-size-xs);
  }

  .details dt {
    color: var(--color-text-muted);
  }

  .details dd {
    margin: 0;
    color: var(--color-text-primary);
  }

  .busy {
    padding: var(--space-2) var(--space-3);
    background: var(--color-warning-bg);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
  }

  .busy p {
    margin: 0 0 var(--space-1);
    color: var(--color-text-primary);
  }

  .busy ul,
  .migration-list {
    margin: 0;
    padding-left: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .ready {
    font-size: var(--font-size-xs);
    color: var(--color-success);
    margin: 0;
  }

  .note {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  .file-input {
    font-size: var(--font-size-sm);
  }

</style>
