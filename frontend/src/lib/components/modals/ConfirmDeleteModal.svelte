<script>
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';

  let { open = false, onclose, onconfirm, title = 'Confirm Delete', message = '', entityName = '' } = $props();

  let noteText = $derived(message || 'The entity will be soft-deleted. Historical data and relationships will be preserved.');

  let submitting = $state(false);

  async function handleConfirm() {
    submitting = true;
    try {
      await onconfirm?.();
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} {title} size="sm">
  <div class="confirm-body">
    <p class="confirm-message">
      Are you sure you want to delete <strong>{entityName || 'this item'}</strong>?
    </p>
    <p class="confirm-note">{noteText}</p>
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
      <Button variant="danger" onclick={handleConfirm} disabled={submitting}>
        {submitting ? 'Deleting...' : 'Delete'}
      </Button>
    </div>
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

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
