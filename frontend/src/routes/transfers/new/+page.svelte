<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { transfer as transferTutorial } from '$lib/tutorial/definitions/index';
  import transferMock from '$lib/tutorial/mocks/transfer';

  tutorialStore.registerMock('transfer', transferMock);

  let loading = $state(true);
  let error = $state(null);
  let success = $state(null);
  let entities = $state([]);
  let currencies = $state([]);

  let fromEntityId = $state('');
  let toEntityId = $state('');
  let amount = $state('');
  let currency = $state('EUR');
  let timestamp = $state(new Date().toISOString().slice(0, 16));
  let notes = $state('');

  let submitting = $state(false);

  async function loadOptions() {
    loading = true;
    try {
      const [entityList, currencyList] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
      ]);
      entities = entityList;
      currencies = currencyList;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'options' });
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!fromEntityId || !toEntityId || !amount || !timestamp) {
      error = t('transfer.validationRequired');
      return;
    }
    if (fromEntityId === toEntityId) {
      error = t('transfer.validationSame');
      return;
    }
    submitting = true;
    error = '';
    success = null;
    try {
      await api.post('/transfers', {
        from_entity_id: parseInt(fromEntityId),
        to_entity_id: parseInt(toEntityId),
        amount: parseFloat(amount),
        currency,
        timestamp: new Date(timestamp).toISOString(),
        notes: notes || null,
      });
      success = t('transfer.success');
      fromEntityId = '';
      toEntityId = '';
      amount = '';
      notes = '';
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'transfer' });
    } finally {
      submitting = false;
    }
  }

  onMount(() => {
    loadOptions();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('transfer'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('transfer');
    if (on && !_tutWasOn) loadOptions();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('transfer.title')}</h1>
    <ReplayButton page="transfer" />
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('transfer.loading')} />
{:else}
  <div class="transfer-form">
    <div class="form-card">
      <h2 class="form-title">{t('transfer.formTitle')}</h2>
      <p class="form-description">{t('transfer.formDesc')}</p>

      <div class="form-grid">
        <div class="entity-select">
          <label class="field-label" for="transfer-from">{t('transfer.fromEntity')}</label>
          <Select
            id="transfer-from"
            bind:value={fromEntityId}
            options={[{ value: '', label: t('transfer.selectSource') }, ...entities.map(e => ({ value: String(e.id), label: e.name }))]}
          />
        </div>

        <div class="transfer-arrow">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </div>

        <div class="entity-select">
          <label class="field-label" for="transfer-to">{t('transfer.toEntity')}</label>
          <Select
            id="transfer-to"
            bind:value={toEntityId}
            options={[{ value: '', label: t('transfer.selectDest') }, ...entities.map(e => ({ value: String(e.id), label: e.name }))]}
          />
        </div>
      </div>

      <div class="form-grid-three">
        <div>
          <label class="field-label" for="transfer-amount">{t('transfer.amount')}</label>
          <input
            id="transfer-amount"
            type="number"
            class="field-input"
            bind:value={amount}
            min="0"
            step="any"
            placeholder={t('transfer.amountPlaceholder')}
          />
        </div>
        <div>
          <label class="field-label" for="transfer-currency">{t('transfer.currency')}</label>
          <Select
            id="transfer-currency"
            bind:value={currency}
            options={currencies.map(c => ({ value: c, label: c }))}
          />
        </div>
        <div>
          <label class="field-label" for="transfer-datetime">{t('transfer.dateTime')}</label>
          <input
            id="transfer-datetime"
            type="datetime-local"
            class="field-input"
            bind:value={timestamp}
            disabled={submitting}
          />
        </div>
      </div>

      <div>
        <label class="field-label" for="transfer-notes">{t('transfer.notes')}</label>
        <input
          id="transfer-notes"
          type="text"
          class="field-input"
          bind:value={notes}
          placeholder={t('transfer.notesPlaceholder')}
        />
      </div>

      {#if error}
        <div class="form-error">{error}</div>
      {/if}

      {#if success}
        <div class="form-success">{success}</div>
      {/if}

      <div class="form-actions">
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('transfer.creatingBtn') : t('transfer.createBtn')}
        </Button>
      </div>
    </div>
  </div>
{/if}

<TutorialOverlay definition={transferTutorial} page="transfer" onfinish={() => {}} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .transfer-form {
    max-width: 640px;
  }

  .form-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .form-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    margin: 0;
  }

  .form-description {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin: 0;
    line-height: 1.5;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: var(--space-4);
    align-items: end;
  }

  .form-grid-three {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: var(--space-4);
  }

  .transfer-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    padding-bottom: var(--space-2);
    color: var(--color-text-muted);
  }

  .field-label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-secondary);
    margin-bottom: var(--space-2);
  }

  .field-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    background: var(--color-surface);
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: -1px;
    border-color: var(--color-primary);
  }

  .form-error {
    font-size: var(--font-size-sm);
    color: var(--color-danger);
    padding: var(--space-3);
    background: rgba(224, 49, 49, 0.05);
    border-radius: var(--radius-md);
  }

  .form-success {
    font-size: var(--font-size-sm);
    color: var(--color-success);
    padding: var(--space-3);
    background: rgba(47, 158, 68, 0.05);
    border-radius: var(--radius-md);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
  }

  @media (max-width: 640px) {
    .form-grid {
      grid-template-columns: 1fr;
    }

    .transfer-arrow {
      transform: rotate(90deg);
      padding: 0;
    }

    .form-grid-three {
      grid-template-columns: 1fr;
    }
  }
</style>
