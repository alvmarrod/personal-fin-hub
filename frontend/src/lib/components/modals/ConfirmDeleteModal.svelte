<script>
  import { t } from '$lib/i18n/index.svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormActions from '$lib/components/FormActions.svelte';

  let { open = false, onclose, onconfirm, title = t('common.confirmDelete'), message = '', entityName = '' } = $props();

  let noteText = $derived(message || t('common.confirmDeleteFallback'));

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
      error = e?.message || t('modals.createFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} {title} size="sm">
  <div class="confirm-body">
    <p class="confirm-message">
      {t('common.confirmDeleteMsg', { name: entityName || t('common.confirmDeleteDefault') })}
    </p>
    <p class="confirm-note">{noteText}</p>
    {#if error}
      <p class="confirm-error">{error}</p>
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="danger" onclick={handleConfirm} disabled={submitting}>
        {submitting ? t('common.deleting') : t('common.delete')}
      </Button>
    </FormActions>
  </div>
</Modal>

<style>
  .confirm-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .confirm-message {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.5;
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

</style>
