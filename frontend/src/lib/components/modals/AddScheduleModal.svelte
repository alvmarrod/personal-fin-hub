<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
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
  let currencies = $state([]);

  let description = $state('');
  let startDate = $state(new Date().toISOString().split('T')[0]);
  let endDate = $state('');
  let periodicityType = $state('MONTHLY');
  let customCron = $state('');
  let entityId = $state('');
  let currency = $state('EUR');
  let txType = $state('MONEY_IN');
  let totalValue = $state('');
  let notes = $state('');

  let PERIODICITY_TYPES = $derived([
    { value: 'ONE_OFF', label: t('schedules.typeOneOff') },
    { value: 'DAILY', label: t('schedules.typeDaily') },
    { value: 'WEEKLY', label: t('schedules.typeWeekly') },
    { value: 'MONTHLY', label: t('schedules.typeMonthly') },
    { value: 'QUARTERLY', label: t('schedules.typeQuarterly') },
    { value: 'ANNUALLY', label: t('schedules.typeAnnually') },
    { value: 'CUSTOM', label: t('schedules.typeCustom') },
  ]);

  let TX_TYPES = $derived([
    { value: 'MONEY_IN', label: t('schedules.filterMoneyIn') },
    { value: 'MONEY_OUT', label: t('schedules.filterMoneyOut') },
    { value: 'INVESTMENT_BUY', label: t('schedules.filterInvestmentBuy') },
    { value: 'INVESTMENT_SELL', label: t('schedules.filterInvestmentSell') },
    { value: 'DIVIDEND', label: t('schedules.filterDividend') },
    { value: 'INTEREST', label: t('schedules.filterInterest') },
  ]);

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, currencyList] = await Promise.all([
        crud.entities.getList(),
        import('../../api/analytics').then(m => m.currenciesApi.getList()),
      ]);
      entities = entityList;
      currencies = currencyList;
    } catch (e) {
      error = 'Failed to load options';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!description || !startDate || !totalValue) {
      error = 'Description, start date, and total value are required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.schedules.create({
        description,
        start_date: startDate,
        end_date: endDate || null,
        periodicity_type: periodicityType,
        custom_cron: periodicityType === 'CUSTOM' ? customCron : null,
        entity_id: entityId ? parseInt(entityId) : null,
        currency: currency || null,
        type: txType || null,
        total_value: parseFloat(totalValue),
        notes: notes || null,
      });
      reset();
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to create schedule';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    description = '';
    startDate = new Date().toISOString().split('T')[0];
    endDate = '';
    periodicityType = 'MONTHLY';
    customCron = '';
    entityId = '';
    currency = 'EUR';
    txType = 'MONEY_IN';
    totalValue = '';
    notes = '';
  }

  $effect(() => {
    if (open) {
      reset();
      loadOptions();
    }
  });
</script>

<Modal {open} {onclose} title={t('modals.addSchedule')} size="md">
  {#if loading}
    <p class="loading-text">Loading...</p>
  {:else}
    <div class="form">
      <FormField label={t('common.description')} required>
        <TextInput bind:value={description} placeholder="e.g. Monthly Salary" />
      </FormField>
      <div class="form-row">
        <FormField label={t('modals.startDate')} required>
          <TextInput type="date" bind:value={startDate} />
        </FormField>
        <FormField label={t('modals.endDate')}>
          <TextInput type="date" bind:value={endDate} />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label={t('modals.periodicity')} required>
          <Select bind:value={periodicityType} options={PERIODICITY_TYPES} />
        </FormField>
        <FormField label={t('common.type')}>
          <Select bind:value={txType} options={TX_TYPES} />
        </FormField>
      </div>
      {#if periodicityType === 'CUSTOM'}
        <FormField label="Custom Cron Expression" required>
          <TextInput bind:value={customCron} placeholder="e.g. 0 9 1 * *" />
        </FormField>
      {/if}
      <div class="form-row">
        <FormField label={t('modals.entity')}>
          <Select
            bind:value={entityId}
            options={[{ value: '', label: 'None' }, ...entities.map(e => ({ value: String(e.id), label: e.name }))]}
          />
        </FormField>
        <FormField label={t('common.currency')}>
          <Select
            bind:value={currency}
            options={currencies.map(c => ({ value: c, label: c }))}
          />
        </FormField>
      </div>
      <FormField label={t('modals.value')} required>
        <NumberInput bind:value={totalValue} min="0" step="any" placeholder="e.g. 500" />
      </FormField>
      <FormField label={t('common.notes')}>
        <TextInput bind:value={notes} placeholder={t('modals.notesPlaceholder')} />
      </FormField>
      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>
    </div>
  {/if}
</Modal>

<style>
  .loading-text {
    text-align: center;
    color: var(--color-text-muted);
    padding: var(--space-6);
  }

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
