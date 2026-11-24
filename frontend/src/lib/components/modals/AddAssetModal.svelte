<script>
  import { onMount } from 'svelte';
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { crud } from '../../api/analytics';
  import { displayTimezone } from '$lib/preferences/timezone.svelte';
  import { fromZonedInput, todayInZone } from '$lib/utils/time.js';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

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
  let currency = $state('EUR');
  let date = $state(todayInZone(displayTimezone()));
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
      error = t('common.errorPrefix', { resource: 'options' });
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
        timestamp: fromZonedInput(`${date}T00:00`, displayTimezone()).toISOString(),
        notes: 'Initial position via quick-add',
      });
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
    marketAssetId = '';
    quantity = '';
    unitPrice = '';
    currency = 'EUR';
    date = todayInZone(displayTimezone());
    notes = '';
  }

  $effect(() => {
    if (open) loadOptions();
  });
</script>

<Modal {open} {onclose} title={t('modals.addAsset')} size="md">
  {#if loading}
    <p style="text-align:center;color:var(--color-text-muted)">{t('common.loading')}</p>
  {:else}
    <ModalForm>
      <FormField label={t('common.entity')} required>
        <Select bind:value={entityId} options={entities} placeholder="Select entity" />
      </FormField>
      <FormField label="Market Asset" required>
        <Select bind:value={marketAssetId} options={marketAssets} placeholder="Select asset" />
      </FormField>
      <div class="form-row">
        <FormField label={t('modals.quantity')} required>
          <NumberInput bind:value={quantity} min="0" step="any" placeholder="e.g. 10" />
        </FormField>
        <FormField label={t('modals.unitPrice')} required>
          <NumberInput bind:value={unitPrice} min="0" step="any" placeholder="e.g. 150.50" />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label={t('common.currency')} required>
          <TextInput bind:value={currency} placeholder="EUR" />
        </FormField>
        <FormField label={t('modals.date')} required>
          <TextInput type="date" bind:value={date} />
        </FormField>
      </div>
      <FormField label={t('common.notes')}>
        <TextInput bind:value={notes} placeholder={t('modals.notesPlaceholder')} />
      </FormField>
      {#if error}
        <FormError message={error} />
      {/if}
      <FormActions>
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.creating') : t('modals.addAsset')}
        </Button>
      </FormActions>
    </ModalForm>
  {/if}
</Modal>

<style>

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

</style>
