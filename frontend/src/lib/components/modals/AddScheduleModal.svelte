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
  import { displayTimezone } from '$lib/preferences/timezone.svelte';
  import { todayInZone } from '$lib/utils/time.js';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let currencies = $state([]);
  let portfolioAssets = $state([]);

  let description = $state('');
  let startDate = $state(todayInZone(displayTimezone()));
  let endDate = $state('');
  let periodicityType = $state('MONTHLY');
  let customCron = $state('');
  let entityId = $state('');
  let currency = $state('EUR');
  let txType = $state('INCOME');
  let totalValue = $state('');
  let portfolioAssetId = $state('');
  let notes = $state('');

  let isInvestmentType = $derived(['INVESTMENT_BUY', 'INVESTMENT_SELL'].includes(txType));
  let isIncomeType = $derived(txType === 'INCOME');
  let incomeCategory = $state('');

  let selectedEntity = $derived(entities.find(e => String(e.id) === entityId) || null);
  let singleCurrency = $derived(
    selectedEntity?.supports_multi_currency === false ? selectedEntity.main_currency : null
  );

  $effect(() => {
    if (singleCurrency && !isInvestmentType) currency = singleCurrency;
  });

  let incomeCategoryOptions = $derived([
    { value: '', label: 'None' },
    { value: 'salary', label: t('income.category.salary') },
    { value: 'other', label: t('income.category.other') },
    { value: 'dividends', label: t('income.category.dividends') },
    { value: 'interest', label: t('income.category.interest') },
    { value: 'cashback', label: t('income.category.cashback') },
  ]);

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
    { value: 'INCOME', label: t('schedules.filterMoneyIn') },
    { value: 'MONEY_OUT', label: t('schedules.filterMoneyOut') },
    { value: 'INVESTMENT_BUY', label: t('schedules.filterInvestmentBuy') },
    { value: 'INVESTMENT_SELL', label: t('schedules.filterInvestmentSell') },
  ]);

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, currencyList, paList] = await Promise.all([
        crud.entities.getList(),
        import('../../api/analytics').then(m => m.currenciesApi.getList()),
        crud.portfolioAssets.getList(),
      ]);
      entities = entityList;
      currencies = currencyList;
      portfolioAssets = paList;
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
        income_category: incomeCategory || null,
        total_value: parseFloat(totalValue),
        portfolio_asset_id: portfolioAssetId ? parseInt(portfolioAssetId) : null,
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
    startDate = todayInZone(displayTimezone());
    endDate = '';
    periodicityType = 'MONTHLY';
    customCron = '';
    entityId = '';
    currency = 'EUR';
    txType = 'INCOME';
    incomeCategory = '';
    totalValue = '';
    portfolioAssetId = '';
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
    <ModalForm>
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
            disabled={!!singleCurrency && !isInvestmentType}
          />
          {#if singleCurrency && !isInvestmentType}
            <p class="field-hint">{t('modals.singleCurrencyLocked', { currency: singleCurrency })}</p>
          {/if}
        </FormField>
      </div>
      {#if isIncomeType}
        <FormField label={t('income.category')}>
          <Select bind:value={incomeCategory} options={incomeCategoryOptions} />
        </FormField>
      {/if}
      <FormField label={t('modals.value')} required>
        <NumberInput bind:value={totalValue} min="0" step="any" placeholder="e.g. 500" />
      </FormField>
      {#if isInvestmentType}
        <FormField label={t('modals.asset')} required>
          <Select
            bind:value={portfolioAssetId}
            options={[
              { value: '', label: 'Select asset...' },
              ...portfolioAssets.map(a => ({ value: String(a.id), label: a.market_code }))
            ]}
          />
        </FormField>
      {/if}
      <FormField label={t('common.notes')}>
        <TextInput bind:value={notes} placeholder={t('modals.notesPlaceholder')} />
      </FormField>
      {#if error}
        <FormError message={error} />
      {/if}
      <FormActions>
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </FormActions>
    </ModalForm>
  {/if}
</Modal>

<style>
  .loading-text {
    text-align: center;
    color: var(--color-text-muted);
    padding: var(--space-6);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

  .field-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    margin: 0;
  }

</style>
