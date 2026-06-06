<script>
  import { onMount } from 'svelte';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import Select from '$lib/components/Select.svelte';
  import NumberInput from '$lib/components/NumberInput.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import Button from '$lib/components/Button.svelte';

  let { open, onclose, onsuccess } = $props();

  let entityId = $state('');
  let currency = $state('');
  let amount = $state('');
  let timestamp = $state('');
  let notes = $state('');
  let submitting = $state(false);
  let error = $state(null);

  let entities = $state([]);
  let currencies = $state([]);

  $effect(() => {
    if (open) {
      loadOptions();
      reset();
    }
  });

  async function loadOptions() {
    try {
      const [entitiesData, currenciesData] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
      ]);
      entities = entitiesData || [];
      currencies = (currenciesData || []).sort();
    } catch (e) {
      error = 'Failed to load options';
    }
  }

  function reset() {
    entityId = '';
    currency = '';
    amount = '';
    timestamp = new Date().toISOString().slice(0, 16);
    notes = '';
    error = null;
  }

  async function handleSubmit() {
    if (!entityId || !currency || !amount || !timestamp) {
      error = 'All fields are required';
      return;
    }

    submitting = true;
    error = null;

    try {
      await crud.balanceSnapshots.create({
        entity_id: parseInt(entityId),
        currency,
        amount: parseFloat(amount),
        timestamp: new Date(timestamp).toISOString(),
        notes: notes || null,
      });
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to create balance snapshot';
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} onclose={onclose} title="Add Balance Snapshot" size="md">
  <div class="form">
    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    <FormField label="Entity" required>
      <Select value={entityId} options={entities.map(e => ({ value: String(e.id), label: e.name }))} onchange={(e) => entityId = e.target.value} />
    </FormField>

    <FormField label="Currency" required>
      <Select value={currency} options={currencies.map(c => ({ value: c, label: c }))} onchange={(e) => currency = e.target.value} />
    </FormField>

    <div class="form-row">
      <FormField label="Amount" required>
        <NumberInput value={amount} onchange={(e) => amount = e.target.value} placeholder="0.00" />
      </FormField>

      <FormField label="Timestamp" required>
        <input type="datetime-local" bind:value={timestamp} class="datetime-input" />
      </FormField>
    </div>

    <FormField label="Notes">
      <TextInput value={notes} onchange={(e) => notes = e.target.value} placeholder="Optional notes..." />
    </FormField>

    <div class="form-actions">
      <Button variant="secondary" onclick={onclose}>Cancel</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? 'Creating...' : 'Create Snapshot'}
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

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

  .datetime-input {
    width: 100%;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .error-message {
    background: rgba(224, 49, 49, 0.1);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
</style>
