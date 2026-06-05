<script>
  import { onMount } from 'svelte';
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';

  let { open = false, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);

  let entityId = $state('');
  let amount = $state('');
  let currency = $state('USD');
  let date = $state(new Date().toISOString().split('T')[0]);
  let description = $state('');
  let frequency = $state('ONE_OFF');

  let frequencyOptions = [
    { value: 'ONE_OFF', label: 'One Time' },
    { value: 'MONTHLY', label: 'Monthly' },
  ];

  async function loadOptions() {
    loading = true;
    try {
      const list = await crud.entities.getList();
      entities = list.map(e => ({ value: e.id, label: e.name }));
    } catch (e) {
      error = 'Failed to load entities';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!entityId || !amount || !date) {
      error = 'Please fill all required fields';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.transactions.create({
        entity_id: parseInt(entityId),
        type: 'MONEY_IN',
        amount: parseFloat(amount),
        currency,
        transaction_date: date,
        description: description || null,
        frequency,
      });
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to add income';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    entityId = '';
    amount = '';
    currency = 'USD';
    date = new Date().toISOString().split('T')[0];
    description = '';
    frequency = 'ONE_OFF';
  }

  $effect(() => {
    if (open) loadOptions();
  });
</script>

<Modal {open} {onclose} title="Add Income" size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">Loading...</p>
  {:else}
    <div class="form">
      <FormField label="Entity" required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>
      <FormField label="Amount" required>
        <NumberInput bind:value={amount} min="0" step="any" placeholder="e.g. 5000" />
      </FormField>
      <div class="form-row">
        <FormField label="Currency" required>
          <TextInput bind:value={currency} placeholder="USD" />
        </FormField>
        <FormField label="Date" required>
          <TextInput type="date" bind:value={date} />
        </FormField>
      </div>
      <FormField label="Description">
        <TextInput bind:value={description} placeholder="Salary, freelance, etc." />
      </FormField>
      <FormField label="Frequency">
        <Select bind:value={frequency} options={frequencyOptions} />
      </FormField>
      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? 'Adding...' : 'Add Income'}
        </Button>
      </div>
    </div>
  {/if}
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
