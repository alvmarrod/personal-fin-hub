<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { currenciesApi } from '../../api/analytics';

  let { open = false, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let code = $state('');

  async function handleSubmit() {
    if (!code) {
      error = 'Currency code is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await currenciesApi.create(code.toUpperCase());
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to add currency';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    code = '';
  }
</script>

<Modal {open} {onclose} title="Add Currency" size="sm">
  <div class="form">
    <FormField label="Currency Code" required>
      <TextInput bind:value={code} placeholder="e.g. EUR" style="text-transform:uppercase" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? 'Adding...' : 'Add Currency'}
      </Button>
    </div>
  </div>
</Modal>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-error {
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
