<script>
  import { t } from '$lib/i18n/index.svelte';
  import { api } from '$lib/api/client.js';
  import { formatPercent } from '$lib/utils/format.svelte';
  import { STRATEGY_BUCKETS, emptyTargets } from '$lib/utils/strategy.js';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import NumberInput from '../NumberInput.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';

  let { open = false, onclose, target = null, defaultDate = '', onsaved } = $props();

  let effectiveFrom = $state('');
  let targets = $state(emptyTargets());
  let submitting = $state(false);
  let error = $state('');

  let editing = $derived(target != null);
  let total = $derived(STRATEGY_BUCKETS.reduce((sum, bucket) => sum + (Number(targets[bucket]) || 0), 0));
  let totalOk = $derived(Math.abs(total - 100) <= 0.01);
  let canSave = $derived(!submitting && totalOk && !!effectiveFrom);

  function localDate() {
    return new Date().toISOString().slice(0, 10);
  }

  $effect(() => {
    if (!open) return;
    effectiveFrom = target?.effective_from ?? (defaultDate || localDate());
    targets = target ? { ...emptyTargets(), ...target.targets } : emptyTargets();
    error = '';
  });

  async function save() {
    if (!canSave) return;
    submitting = true;
    error = '';
    const body = {
      effective_from: effectiveFrom,
      targets: Object.fromEntries(STRATEGY_BUCKETS.map((bucket) => [bucket, Number(targets[bucket]) || 0])),
    };
    try {
      if (editing) {
        await api.put(`/strategy/${encodeURIComponent(target.effective_from)}`, body);
      } else {
        await api.post('/strategy', body);
      }
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e?.message || t('strategy.saveFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={editing ? t('strategy.modalEditTitle') : t('strategy.modalAddTitle')} size="sm">
  <div class="strategy-form">
    <FormField label={t('strategy.effectiveFrom')} required>
      <input class="date-input" type="date" bind:value={effectiveFrom} disabled={editing} />
    </FormField>
    {#if editing}
      <p class="hint">{t('strategy.dateLocked')}</p>
    {/if}

    <fieldset class="targets">
      <legend>{t('strategy.targetsLabel')}</legend>
      {#each STRATEGY_BUCKETS as bucket (bucket)}
        <div class="target-row">
          <label for="target-{bucket}">{t(`bucket.${bucket}`)}</label>
          <NumberInput id="target-{bucket}" bind:value={targets[bucket]} min="0" max="100" step="0.01" />
        </div>
      {/each}
    </fieldset>

    <p class="total" class:bad={!totalOk}>
      {totalOk
        ? formatPercent(total)
        : t('strategy.badTotal', { total: formatPercent(total) })}
    </p>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={save} disabled={!canSave}>
        {submitting ? t('strategy.saving') : t('strategy.save')}
      </Button>
    </FormActions>
  </div>
</Modal>

<style>
  .strategy-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .date-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font-family: inherit;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    height: 40px;
  }

  .hint {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .targets {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .targets legend {
    padding: 0 var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .target-row {
    display: grid;
    grid-template-columns: 1fr 110px;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--font-size-sm);
  }

  .total {
    margin: 0;
    text-align: right;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-success);
  }

  .total.bad {
    color: var(--color-danger);
  }

</style>
