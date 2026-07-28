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
  let marketAssets = $state([]);

  let marketCode = $state('');
  let distributionType = $state('');
  let dcaStatus = $state('');
  let layer = $state('');
  let tactic = $state(false);
  let desiredWeight = $state('');
  let ter = $state('');
  let trackingMode = $state('auto');
  let currentManualValue = $state('');
  let isActive = $state(true);
  let notes = $state('');

  let DISTRIBUTION_TYPES = $derived([
    { value: '', label: 'None' },
    { value: 'accumulation', label: 'Accumulation' },
    { value: 'distribution', label: t('modals.distribution') },
    { value: 'N/A', label: 'N/A' },
  ]);

  const DCA_STATUSES = [
    { value: '', label: 'None' },
    { value: 'ongoing', label: 'Ongoing' },
    { value: 'paused', label: 'Paused' },
    { value: 'closed', label: 'Closed' },
  ];

  let LAYERS = $derived([
    { value: '', label: 'None' },
    { value: 'core', label: t('modals.layerCore') },
    { value: 'reserve', label: t('modals.layerReserve') },
    { value: 'satellite', label: t('modals.layerSatellite') },
  ]);

  const TRACKING_MODES = [
    { value: 'auto', label: 'Auto' },
    { value: 'manual', label: 'Manual' },
  ];

  async function loadOptions() {
    loading = true;
    try {
      marketAssets = await crud.marketAssets.getList();
    } catch (e) {
      error = 'Failed to load market assets';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!marketCode) {
      error = 'Market asset is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.portfolioAssets.create({
        market_code: marketCode,
        distribution_type: distributionType || null,
        dca_status: dcaStatus || null,
        layer: layer || null,
        tactic,
        desired_weight: desiredWeight ? parseFloat(desiredWeight) : null,
        ter: ter ? parseFloat(ter) : null,
        tracking_mode: trackingMode,
        current_value_manual: currentManualValue ? parseFloat(currentManualValue) : null,
        is_active: isActive,
        notes: notes || null,
      });
      reset();
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to create portfolio asset';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    marketCode = '';
    distributionType = '';
    dcaStatus = '';
    layer = '';
    tactic = false;
    desiredWeight = '';
    ter = '';
    trackingMode = 'auto';
    currentManualValue = '';
    isActive = true;
    notes = '';
  }

  $effect(() => {
    if (open) {
      reset();
      loadOptions();
    }
  });
</script>

<Modal {open} {onclose} title={t('modals.addPortfolioAsset')} size="md">
  {#if loading}
    <p class="loading-text">Loading market assets...</p>
  {:else}
    <div class="form">
      <FormField label={t('modals.marketCode')} required>
        <Select
          bind:value={marketCode}
          options={marketAssets.map(ma => ({ value: ma.market_code, label: `${ma.market_code} — ${ma.name || ma.ticker || ''}` }))}
          placeholder="Select market asset"
        />
      </FormField>
      <div class="form-row">
        <FormField label={t('modals.layer')}>
          <Select bind:value={layer} options={LAYERS} />
        </FormField>
        <FormField label={t('modals.dca')}>
          <Select bind:value={dcaStatus} options={DCA_STATUSES} />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label={t('modals.distribution')}>
          <Select bind:value={distributionType} options={DISTRIBUTION_TYPES} />
        </FormField>
        <FormField label="Tracking Mode">
          <Select bind:value={trackingMode} options={TRACKING_MODES} />
        </FormField>
      </div>
      <div class="form-row">
        <FormField label={t('modals.desiredPct')}>
          <NumberInput bind:value={desiredWeight} min="0" max="100" step="any" placeholder="e.g. 25" />
        </FormField>
        <FormField label={t('modals.ter')}>
          <NumberInput bind:value={ter} min="0" step="any" placeholder="e.g. 0.07" />
        </FormField>
      </div>
      {#if trackingMode === 'manual'}
        <FormField label="Manual Value">
          <NumberInput bind:value={currentManualValue} min="0" step="any" placeholder="e.g. 10000" />
        </FormField>
      {/if}
      <div class="form-row">
        <div class="checkbox-field">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={tactic} />
            Tactic
          </label>
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={isActive} />
            Active
          </label>
        </div>
      </div>
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

  .checkbox-field {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding-top: var(--space-6);
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    cursor: pointer;
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
