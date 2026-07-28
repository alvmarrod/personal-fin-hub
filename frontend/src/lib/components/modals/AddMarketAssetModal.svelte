<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { crud, currenciesApi } from '../../api/analytics';

  let { open = false, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let marketCode = $state('');
  let ticker = $state('');
  let assetType = $state('STOCK');
  let assetClass = $state('');
  let currencyCode = $state('EUR');
  let name = $state('');
  let description = $state('');
  let exchange = $state('');
  let currencies = $state([]);

  const ASSET_TYPES = [
    { value: 'STOCK', label: 'Stock' },
    { value: 'ETF', label: 'ETF' },
    { value: 'ETC', label: 'ETC' },
    { value: 'FUND', label: 'Fund' },
    { value: 'INDEX FUND', label: 'Index Fund' },
    { value: 'CURRENCY', label: 'Currency' },
    { value: 'CRYPTO', label: 'Crypto' },
    { value: 'OTHER', label: 'Other' },
  ];

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

  async function handleSubmit() {
    if (!marketCode || !name) {
      error = 'Market code and name are required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.marketAssets.create({
        market_code: marketCode,
        ticker: ticker || null,
        asset_type: assetType,
        asset_class: assetClass || null,
        currency_code: currencyCode,
        name: name,
        description: description || null,
        exchange: exchange || null,
      });
      reset();
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to create market asset';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    marketCode = '';
    ticker = '';
    assetType = 'STOCK';
    assetClass = '';
    currencyCode = 'EUR';
    name = '';
    description = '';
    exchange = '';
  }

  $effect(() => {
    if (open) {
      reset();
      loadCurrencies();
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
</script>

<Modal {open} {onclose} title="Add Market Asset" size="md">
  <div class="form">
    <div class="form-row">
      <FormField label="Market Code" required>
        <TextInput bind:value={marketCode} placeholder="e.g. AAPL" />
      </FormField>
      <FormField label="Ticker">
        <TextInput bind:value={ticker} placeholder="e.g. AAPL" />
      </FormField>
    </div>
    <FormField label="Name" required>
      <TextInput bind:value={name} placeholder="e.g. Apple Inc." />
    </FormField>
    <div class="form-row">
      <FormField label="Asset Type" required>
        <Select bind:value={assetType} options={ASSET_TYPES} />
      </FormField>
      <FormField label="Asset Class">
        <Select bind:value={assetClass} options={ASSET_CLASSES} />
      </FormField>
    </div>
    <div class="form-row">
      <FormField label="Currency" required>
        <Select value={currencyCode} options={currencies.map(c => ({ value: c, label: c }))} onchange={(e) => currencyCode = e.target.value} />
      </FormField>
      <FormField label="Exchange">
        <TextInput bind:value={exchange} placeholder="e.g. NASDAQ" />
      </FormField>
    </div>
    <FormField label="Description">
      <TextInput bind:value={description} placeholder="Optional description" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? 'Creating...' : 'Create Asset'}
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
