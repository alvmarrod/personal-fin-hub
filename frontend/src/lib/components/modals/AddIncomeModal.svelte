<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { crud, currenciesApi } from '../../api/analytics';
  import { api } from '../../api/client';

  let { open = false, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let currencyOptions = $state([]);

  let mode = $state('one_time');
  let entityId = $state('');
  let amount = $state('');
  let currency = $state('EUR');
  let date = $state(new Date().toISOString().split('T')[0]);
  let description = $state('');
  let incomeCategory = $state('salary');
  let frequency = $state('MONTHLY');
  let startDate = $state(new Date().toISOString().split('T')[0]);
  let endDate = $state('');

  let incomeCategoryOptions = $derived([
    { value: 'salary', label: t('income.category.salary') },
    { value: 'other', label: t('income.category.other') },
    { value: 'dividends', label: t('income.category.dividends') },
    { value: 'interest', label: t('income.category.interest') },
    { value: 'cashback', label: t('income.category.cashback') },
  ]);

  let frequencyOptions = $derived([
    { value: 'MONTHLY', label: t('schedules.typeMonthly') },
    { value: 'QUARTERLY', label: t('schedules.typeQuarterly') },
    { value: 'ANNUALLY', label: t('schedules.typeAnnually') },
  ]);

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, codes] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
      ]);
      entities = entityList.map(e => ({ value: e.id, label: e.name }));
      currencyOptions = codes.map(c => ({ value: c, label: c }));
      if (!currencyOptions.find(o => o.value === currency)) {
        currency = codes[0] || 'EUR';
      }
    } catch (e) {
      error = t('common.errorPrefix', { resource: 'options' });
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
          type: 'INCOME',
          entity_id: parseInt(entityId),
          total_value: parseFloat(amount),
          currency,
          timestamp: `${date}T00:00:00`,
          notes: description || null,
          income_category: incomeCategory,
        });
      } else {
        await api.post('/schedules/full', {
          schedule: {
            description: description || 'Recurring Income',
            start_date: startDate,
            end_date: endDate || null,
            periodicity_type: frequency,
            entity_id: parseInt(entityId),
            currency,
            type: 'INCOME',
            total_value: parseFloat(amount),
            notes: description || null,
            income_category: incomeCategory,
          },
        });
      }
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.createFailed');
    } finally {
      submitting = false;
    }
  }

  function reset() {
    entityId = '';
    amount = '';
    currency = 'EUR';
    date = new Date().toISOString().split('T')[0];
    description = '';
    incomeCategory = 'salary';
    frequency = 'MONTHLY';
    startDate = new Date().toISOString().split('T')[0];
    endDate = '';
  }

  $effect(() => {
    if (open) loadOptions();
  });
</script>

<Modal {open} {onclose} title={t('modals.addIncome')} size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">{t('common.loading')}</p>
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

      <FormField label={t('modals.entity')} required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>

      <div class="form-row">
        <FormField label={t('common.amount')} required>
          <NumberInput bind:value={amount} min="0" step="any" placeholder="e.g. 5000" />
        </FormField>
        <FormField label={t('common.currency')} required>
          <Select bind:value={currency} options={currencyOptions} placeholder="Select currency" />
        </FormField>
      </div>

      <FormField label={t('common.description')}>
        <TextInput bind:value={description} placeholder="Salary, freelance, etc." />
      </FormField>

      <FormField label={t('income.category')} required>
        <Select bind:value={incomeCategory} options={incomeCategoryOptions} />
      </FormField>

      {#if mode === 'one_time'}
        <FormField label={t('common.date')} required>
          <TextInput type="date" bind:value={date} />
        </FormField>
      {:else}
        <FormField label="Frequency" required>
          <Select bind:value={frequency} options={frequencyOptions} />
        </FormField>
        <div class="form-row">
          <FormField label={t('modals.startDate')} required>
            <TextInput type="date" bind:value={startDate} />
          </FormField>
          <FormField label={t('modals.endDate')}>
            <TextInput type="date" bind:value={endDate} placeholder="Optional" />
          </FormField>
        </div>
      {/if}

      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.creating') : mode === 'one_time' ? t('modals.addIncome') : t('modals.addIncome')}
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
