<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud, currenciesApi } from '../../api/analytics';
  import { api } from '../../api/client';

  let { open = false, schedule = null, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let currencyOptions = $state([]);

  let entityId = $state('');
  let amount = $state('');
  let currency = $state('USD');
  let description = $state('');
  let frequency = $state('MONTHLY');
  let startDate = $state('');
  let endDate = $state('');

  let frequencyOptions = [
    { value: 'MONTHLY', label: 'Monthly' },
    { value: 'QUARTERLY', label: 'Quarterly' },
    { value: 'ANNUALLY', label: 'Annually' },
  ];

  function populate(s) {
    if (!s) return;
    entityId = String(s.entity_id ?? '');
    amount = String(s.total_value ?? '');
    currency = s.currency || 'USD';
    description = s.description || '';
    frequency = s.periodicity_type || 'MONTHLY';
    startDate = s.start_date ? s.start_date.split('T')[0] : '';
    endDate = s.end_date ? s.end_date.split('T')[0] : '';
  }

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, codes] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
      ]);
      entities = entityList.map(e => ({ value: e.id, label: e.name }));
      currencyOptions = codes.map(c => ({ value: c, label: c }));
    } catch (e) {
      error = 'Failed to load options';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!entityId || !amount || !startDate) {
      error = 'Please fill all required fields';
      return;
    }
    submitting = true;
    error = '';
    try {
      await api.put(`/schedules/${schedule.id}`, {
        description: description || 'Recurring Income',
        start_date: startDate,
        end_date: endDate || null,
        periodicity_type: frequency,
        entity_id: parseInt(entityId),
        currency,
        type: 'MONEY_IN',
        total_value: parseFloat(amount),
        notes: description || null,
      });
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to update schedule';
    } finally {
      submitting = false;
    }
  }

  $effect(() => {
    if (open) {
      loadOptions();
      populate(schedule);
    }
  });
</script>

<Modal {open} {onclose} title="Edit Schedule" size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">Loading...</p>
  {:else}
    <div class="form">
      <FormField label="Entity" required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>

      <div class="form-row">
        <FormField label="Amount" required>
          <NumberInput bind:value={amount} min="0" step="any" placeholder="e.g. 5000" />
        </FormField>
        <FormField label="Currency" required>
          <Select bind:value={currency} options={currencyOptions} />
        </FormField>
      </div>

      <FormField label="Description">
        <TextInput bind:value={description} placeholder="Salary, freelance, etc." />
      </FormField>

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

      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? 'Saving...' : 'Save Changes'}
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
