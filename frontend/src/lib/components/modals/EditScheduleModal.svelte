<script>
  import Modal from '../Modal.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud, currenciesApi } from '../../api/analytics';

  let { open = false, schedule = null, onclose, onsuccess } = $props();

  let loading = $state(false);
  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let currencyOptions = $state([]);
  let portfolioAssets = $state([]);

  let entityId = $state('');
  let amount = $state('');
  let currency = $state('EUR');
  let description = $state('');
  let txType = $state('MONEY_IN');
  let frequency = $state('MONTHLY');
  let startDate = $state('');
  let endDate = $state('');
  let portfolioAssetId = $state('');

  let isInvestmentType = $derived(['INVESTMENT_BUY', 'INVESTMENT_SELL'].includes(txType));

  let PERIODICITY_TYPES = $derived([
    { value: 'ONE_OFF', label: t('schedules.typeOneOff') },
    { value: 'DAILY', label: t('schedules.typeDaily') },
    { value: 'WEEKLY', label: t('schedules.typeWeekly') },
    { value: 'MONTHLY', label: t('schedules.typeMonthly') },
    { value: 'QUARTERLY', label: t('schedules.typeQuarterly') },
    { value: 'ANNUALLY', label: t('schedules.typeAnnually') },
  ]);

  let TX_TYPES = $derived([
    { value: 'MONEY_IN', label: t('schedules.filterMoneyIn') },
    { value: 'MONEY_OUT', label: t('schedules.filterMoneyOut') },
    { value: 'INVESTMENT_BUY', label: t('schedules.filterInvestmentBuy') },
    { value: 'INVESTMENT_SELL', label: t('schedules.filterInvestmentSell') },
    { value: 'DIVIDEND', label: t('schedules.filterDividend') },
    { value: 'INTEREST', label: t('schedules.filterInterest') },
  ]);

  function populate(s) {
    if (!s) return;
    entityId = String(s.entity_id ?? '');
    amount = String(s.total_value ?? '');
    currency = s.currency || 'EUR';
    description = s.description || '';
    txType = s.type || 'MONEY_IN';
    frequency = s.periodicity_type || 'MONTHLY';
    startDate = s.start_date ? s.start_date.split('T')[0] : '';
    endDate = s.end_date ? s.end_date.split('T')[0] : '';
    portfolioAssetId = String(s.portfolio_asset_id ?? '');
  }

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, codes, paList] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
        crud.portfolioAssets.getList(),
      ]);
      entities = entityList.map(e => ({ value: e.id, label: e.name }));
      currencyOptions = codes.map(c => ({ value: c, label: c }));
      portfolioAssets = paList;
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
    if (isInvestmentType && !portfolioAssetId) {
      error = 'Portfolio asset is required for investment schedules';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.schedules.update(schedule.id, {
        description: description || null,
        start_date: startDate,
        end_date: endDate || null,
        periodicity_type: frequency,
        entity_id: parseInt(entityId),
        currency,
        type: txType,
        total_value: parseFloat(amount),
        notes: description || null,
        portfolio_asset_id: portfolioAssetId ? parseInt(portfolioAssetId) : null,
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
      loadOptions().then(() => populate(schedule));
    }
  });
</script>

<Modal {open} {onclose} title={t('modals.editSchedule')} size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">Loading...</p>
  {:else}
    <div class="form">
      <FormField label={t('common.description')}>
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
          <Select bind:value={frequency} options={PERIODICITY_TYPES} />
        </FormField>
        <FormField label={t('common.type')}>
          <Select bind:value={txType} options={TX_TYPES} />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label={t('modals.entity')}>
          <Select bind:value={entityId} options={[{ value: '', label: 'None' }, ...entities]} />
        </FormField>
        <FormField label={t('common.currency')}>
          <Select bind:value={currency} options={currencyOptions} />
        </FormField>
      </div>
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
      <FormField label={t('modals.value')} required>
        <NumberInput bind:value={amount} min="0" step="any" placeholder="e.g. 500" />
      </FormField>
      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
    </div>
  {/if}
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: var(--space-4); }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
  .form-error { color: var(--color-error); font-size: var(--font-size-sm); margin: 0; }
  .form-actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-4); }
</style>
