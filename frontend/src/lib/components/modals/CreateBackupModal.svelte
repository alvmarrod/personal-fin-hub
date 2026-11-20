<script>
  import { t } from '$lib/i18n/index.svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';

  let { open = false, onclose, onconfirm, targets = [] } = $props();

  let submitting = $state(false);
  let error = $state('');

  $effect(() => {
    if (open) error = '';
  });

  async function handleConfirm() {
    submitting = true;
    error = '';
    try {
      await onconfirm?.();
    } catch (e) {
      error = e?.message || t('backups.createFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('backups.createConfirmTitle')} size="sm">
  <div class="confirm-body">
    <p class="confirm-message">{t('backups.createConfirmMsg', { count: targets.length })}</p>
    <ul class="prune-list">
      {#each targets as item (item.name)}
        <li>{item.name}</li>
      {/each}
    </ul>
    <p class="confirm-note">{t('backups.createConfirmNote')}</p>
    {#if error}
      <p class="confirm-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleConfirm} disabled={submitting}>
        {submitting ? t('backups.creating') : t('backups.createNow')}
      </Button>
    </div>
  </div>
</Modal>

<style>
  .confirm-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .confirm-message {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.5;
  }

  .prune-list {
    margin: 0;
    padding: var(--space-2) var(--space-3);
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    list-style: none;
    max-height: 10rem;
    overflow-y: auto;
  }

  .confirm-note {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  .confirm-error {
    font-size: var(--font-size-sm);
    color: var(--color-danger);
    margin: 0;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
