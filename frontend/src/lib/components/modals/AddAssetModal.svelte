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
  let marketAssets = $state([]);

  let entityId = $state('');
  let marketAssetId = $state('');
  let quantity = $state('');
  let unitPrice = $state('');
  let currency = $state('USD');
  let date = $state(new Date().toISOString().split('T')[0]);
  let notes = $state('');

  let incomeAssetClass = $state('VI');

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, assetList] = await Promise.all([
        crud.entities.getList(),
        crud.marketAssets.getList(),
      ]);
      entities = entityList.map(e => ({ value: e.id, label: e.name }));
      marketAssets = assetList.map(a => ({ value: a.id, label: `${a.symbol} — ${a.name}` }));
    } catch (e) {
      error = 'Failed to load options';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!entityId || !marketAssetId || !quantity || !unitPrice || !date) {
      error = 'Please fill all required fields';
      return;
    }
    submitting = true;
    error = '';
    try {
      const asset = await crud.portfolioAssets.create({
        entity_id: parseInt(entityId),
        market_asset_id: parseInt(marketAssetId),
        quantity: parseFloat(quantity),
        notes: notes || null,
      });
      await crud.transactions.create({
        portfolio_asset_id: asset.id,
        type: 'INVESTMENT_BUY',
        quantity: parseFloat(quantity),
        unit_price: parseFloat(unitPrice),
        currency,
        timestamp: `${date}T00:00:00`,
        notes: 'Initial position via quick-add',
      });
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to add asset';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    entityId = '';
    marketAssetId = '';
    quantity = '';
    unitPrice = '';
    currency = 'USD';
    date = new Date().toISOString().split('T')[0];
    notes = '';
  }

  $effect(() => {
    if (open) loadOptions();
  });
</script>

<Modal {open} {onclose} title="Add Asset" size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">Loading...</p>
  {:else}
    <div class="form">
      <FormField label="Entity" required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>
      <FormField label="Market Asset" required>
        <Select bind:value={marketAssetId} options={marketAssets} placeholder="Select asset" />
      </FormField>
      <div class="form-row">
        <FormField label="Quantity" required>
          <NumberInput bind:value={quantity} min="0" step="any" placeholder="e.g. 10" />
        </FormField>
        <FormField label="Unit Price" required>
          <NumberInput bind:value={unitPrice} min="0" step="any" placeholder="e.g. 150.50" />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label="Currency" required>
          <TextInput bind:value={currency} placeholder="USD" />
        </FormField>
        <FormField label="Date" required>
          <TextInput type="date" bind:value={date} />
        </FormField>
      </div>
      <FormField label="Notes">
        <TextInput bind:value={notes} placeholder="Optional notes" />
      </FormField>
      {#if error}
        <p class="form-error">{error}</p>
      {/if}
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? 'Adding...' : 'Add Asset'}
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
