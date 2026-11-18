<script>
  import { onMount } from 'svelte';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import Select from '$lib/components/Select.svelte';
  import NumberInput from '$lib/components/NumberInput.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import Button from '$lib/components/Button.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { displayTimezone } from '$lib/preferences/timezone.svelte';
  import { fromZonedInput, toZonedInput, zoneLabel } from '$lib/utils/time.js';

  let { open, onclose, onsuccess, snapshots = [] } = $props();

  let entityId = $state('');
  let currency = $state('');
  let amount = $state('');
  let timestamp = $state('');
  let maxTimestamp = $state('');
  let notes = $state('');
  let submitting = $state(false);
  let error = $state(null);

  let entities = $state([]);
  let currencies = $state([]);

  // The picker carries no zone: state the one the wall clock belongs to, with
  // the offset in force on the chosen date (DST-aware).
  let zoneHint = $derived(
    t('modals.timeInZone', {
      zone: zoneLabel(displayTimezone(), timestamp ? fromZonedInput(timestamp, displayTimezone()) : new Date()),
    }),
  );

  // Same instant to the second = same anchor: the save replaces it.
  let replaces = $derived.by(() => {
    if (!entityId || !currency || !timestamp) return false;
    const key = fromZonedInput(timestamp, displayTimezone()).toISOString().slice(0, 19);
    return snapshots.some(
      (s) => s.entity_id === parseInt(entityId) && s.currency === currency && String(s.timestamp).slice(0, 19) === key,
    );
  });

  $effect(() => {
    if (open) {
      loadOptions();
      reset();
    }
  });

  async function loadOptions() {
    try {
      const [entitiesData, currenciesData] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
      ]);
      entities = entitiesData || [];
      currencies = (currenciesData || []).sort();
    } catch (e) {
      error = 'Failed to load options';
    }
  }

  function reset() {
    entityId = '';
    currency = '';
    amount = '';
    timestamp = toZonedInput(new Date(), displayTimezone());
    maxTimestamp = toZonedInput(new Date(), displayTimezone());
    notes = '';
    error = null;
  }

  async function handleSubmit() {
    if (!entityId || !currency || !amount || !timestamp) {
      error = 'All fields are required';
      return;
    }

    submitting = true;
    error = null;

    try {
      await crud.balanceSnapshots.create({
        entity_id: parseInt(entityId),
        currency,
        amount: parseFloat(amount),
        timestamp: fromZonedInput(timestamp, displayTimezone()).toISOString(),
        notes: notes || null,
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
</script>

<Modal {open} onclose={onclose} title={t('modals.addBalance')} size="md">
  <div class="form">
    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    <FormField label={t('modals.entity')} required>
      <Select value={entityId} options={entities.map(e => ({ value: String(e.id), label: e.name }))} onchange={(e) => entityId = e.target.value} />
    </FormField>

    <FormField label={t('common.currency')} required>
      <Select value={currency} options={currencies.map(c => ({ value: c, label: c }))} onchange={(e) => currency = e.target.value} />
    </FormField>

    <div class="form-row">
      <FormField label={t('common.amount')} required>
        <NumberInput value={amount} onchange={(e) => amount = e.target.value} placeholder="0.00" />
      </FormField>

      <FormField label={t('modals.date')} required>
        <input type="datetime-local" bind:value={timestamp} max={maxTimestamp} class="datetime-input" />
        <p class="field-hint">{zoneHint}</p>
        {#if replaces}
          <p class="field-hint warn">{t('modals.snapshotSameInstant')}</p>
        {/if}
      </FormField>
    </div>

    <FormField label={t('common.notes')}>
      <TextInput value={notes} onchange={(e) => notes = e.target.value} placeholder={t('modals.notesPlaceholder')} />
    </FormField>

    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.creating') : t('common.create')}
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

  .datetime-input {
    width: 100%;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .field-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    margin: var(--space-1) 0 0;
  }

  .field-hint.warn {
    color: var(--color-warning);
  }

  .error-message {
    background: rgba(224, 49, 49, 0.1);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
</style>
