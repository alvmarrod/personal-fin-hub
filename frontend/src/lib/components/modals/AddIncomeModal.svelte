<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { api } from '../../api/client';

  let { open = false, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);

  let mode = $state('one_time');
  let entityId = $state('');
  let amount = $state('');
  let currency = $state('USD');
  let date = $state(new Date().toISOString().split('T')[0]);
  let description = $state('');
  let frequency = $state('MONTHLY');
  let startDate = $state(new Date().toISOString().split('T')[0]);
  let endDate = $state('');

  let frequencyOptions = [
    { value: 'MONTHLY', label: 'Monthly' },
    { value: 'QUARTERLY', label: 'Quarterly' },
    { value: 'ANNUALLY', label: 'Annually' },
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
    if (!entityId || !amount) {
      error = 'Please fill all required fields';
      return;
    }
    if (mode === 'one_time' && !date) {
      error = 'Please fill all required fields';
      return;
    }
    if (mode === 'recurring' && !startDate) {
      error = 'Please fill all required fields';
      return;
    }
    submitting = true;
    error = '';
    try {
      if (mode === 'one_time') {
        await crud.transactions.create({
          type: 'MONEY_IN',
          entity_id: parseInt(entityId),
          total_value: parseFloat(amount),
          currency,
          timestamp: `${date}T00:00:00`,
          notes: description || null,
        });
      } else {
        await api.post('/schedules/full', {
          schedule: {
            description: description || 'Recurring Income',
            start_date: startDate,
            end_date: endDate || null,
            periodicity_type: frequency,
          },
          transaction: {
            type: 'MONEY_IN',
            entity_id: parseInt(entityId),
            total_value: parseFloat(amount),
            currency,
            timestamp: `${startDate}T00:00:00`,
            notes: description || null,
          },
        });
      }
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
    frequency = 'MONTHLY';
    startDate = new Date().toISOString().split('T')[0];
    endDate = '';
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
      <div class="mode-toggle">
        <button
          class="mode-btn"
          class:mode-btn-active={mode === 'one_time'}
          onclick={() => mode = 'one_time'}
        >One Time</button>
        <button
          class="mode-btn"
          class:mode-btn-active={mode === 'recurring'}
          onclick={() => mode = 'recurring'}
        >Recurring</button>
      </div>

      <FormField label="Entity" required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>

      <div class="form-row">
        <FormField label="Amount" required>
          <NumberInput bind:value={amount} min="0" step="any" placeholder="e.g. 5000" />
        </FormField>
        <FormField label="Currency" required>
          <TextInput bind:value={currency} placeholder="USD" />
        </FormField>
      </div>

      <FormField label="Description">
        <TextInput bind:value={description} placeholder="Salary, freelance, etc." />
      </FormField>

      {#if mode === 'one_time'}
        <FormField label="Date" required>
          <TextInput type="date" bind:value={date} />
        </FormField>
      {:else}
        <FormField label="Frequency" required>
          <Select bind:value={frequency} options={frequencyOptions} />
        </FormField>
        <div class="form-row">
          <FormField label="Start Date" required>
            <TextInput type="date" bind:value={startDate} />
          </FormField>
          <FormField label="End Date">
            <TextInput type="date" bind:value={endDate} placeholder="Optional" />
          </FormField>
        </div>
      {/if}

      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? 'Adding...' : mode === 'one_time' ? 'Add Income' : 'Add Recurring Income'}
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

  .mode-toggle {
    display: flex;
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
    padding: 2px;
    gap: 2px;
  }

  .mode-btn {
    flex: 1;
    padding: var(--space-2) var(--space-4);
    font-family: inherit;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    background: transparent;
    color: var(--color-text-muted);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .mode-btn-active {
    background: var(--color-surface);
    color: var(--color-text-primary);
    box-shadow: var(--shadow-sm);
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
