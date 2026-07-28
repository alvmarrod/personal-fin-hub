<script>
  import Modal from '../Modal.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { crud, currenciesApi } from '../../api/analytics';

  let { open = false, onclose, onsuccess, asset = null } = $props();

  let submitting = $state(false);
  let error = $state('');

  let ticker = $state('');
  let assetType = $state('STOCK');
  let assetClass = $state('');
  let currencyCode = $state('EUR');
  let name = $state('');
  let description = $state('');
  let exchange = $state('');
  let currencies = $state([]);

  let ASSET_TYPES = $derived([
    { value: 'STOCK', label: t('marketAssets.filterStock') },
    { value: 'ETF', label: t('marketAssets.filterETF') },
    { value: 'ETC', label: t('marketAssets.filterETC') },
    { value: 'FUND', label: t('marketAssets.filterFund') },
    { value: 'INDEX FUND', label: t('marketAssets.filterIndexFund') },
    { value: 'CURRENCY', label: t('common.currency') },
    { value: 'CRYPTO', label: t('marketAssets.filterCrypto') },
    { value: 'OTHER', label: t('marketAssets.filterOther') },
  ]);

  const ASSET_CLASSES = [
    { value: '', label: 'None' },
    { value: 'FI', label: 'Fixed Income' },
    { value: 'VI', label: 'Variable Income' },
    { value: 'corp FI', label: 'Corporate FI' },
    { value: 'Sovereign FI', label: 'Sovereign FI' },
    { value: 'mix FI', label: 'Mixed FI' },
    { value: 'REIT', label: 'REIT' },
    { value: 'Gold', label: 'Gold' },
    { value: 'Monetary', label: 'Monetary' },
  ];

  $effect(() => {
    if (open) {
      loadCurrencies();
    }
    if (asset) {
      ticker = asset.ticker || '';
      assetType = asset.asset_type || 'STOCK';
      assetClass = asset.asset_class || '';
      currencyCode = asset.currency_code || 'EUR';
      name = asset.name || '';
      description = asset.description || '';
      exchange = asset.exchange || '';
    }
  });

  async function loadCurrencies() {
    try {
      const data = await currenciesApi.getList();
      currencies = (data || []).sort();
    } catch (e) {
      currencies = [];
    }
  }

  async function handleSubmit() {
    if (!name) {
      error = 'Name is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.marketAssets.update(asset.market_code, {
        market_code: asset.market_code,
        ticker: ticker || null,
        asset_type: assetType,
        asset_class: assetClass || null,
        currency_code: currencyCode,
        name: name,
        description: description || null,
        exchange: exchange || null,
      });
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to update market asset';
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={`${t('modals.editMarketAsset')} — ${asset?.market_code || ''}`} size="md">
  <div class="form">
    <FormField label={t('common.name')} required>
      <TextInput bind:value={name} placeholder="e.g. Apple Inc." />
    </FormField>
    <div class="form-row">
      <FormField label={t('modals.ticker')}>
        <TextInput bind:value={ticker} placeholder="e.g. AAPL" />
      </FormField>
      <FormField label={t('common.currency')}>
        <Select value={currencyCode} options={currencies.map(c => ({ value: c, label: c }))} onchange={(e) => currencyCode = e.target.value} />
      </FormField>
    </div>
    <div class="form-row">
      <FormField label={t('common.type')} required>
        <Select bind:value={assetType} options={ASSET_TYPES} />
      </FormField>
      <FormField label={t('modals.assetClass')}>
        <Select bind:value={assetClass} options={ASSET_CLASSES} />
      </FormField>
    </div>
    <FormField label={t('modals.exchange')}>
      <TextInput bind:value={exchange} placeholder="e.g. NASDAQ" />
    </FormField>
    <FormField label={t('common.description')}>
      <TextInput bind:value={description} placeholder={t('modals.notesPlaceholder')} />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : t('common.create')}
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
