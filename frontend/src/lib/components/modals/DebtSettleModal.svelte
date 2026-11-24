<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import { entities as entityApi } from '$lib/api/analytics.js';
  import { formatAmount, maskAmount } from '$lib/utils/format.svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import NumberInput from '../NumberInput.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, debt = null, onsaved } = $props();

  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let settledAt = $state('');
  let entityId = $state('');
  let amount = $state('');
  let notes = $state('');

  let entityOptions = $derived(entities.map((entity) => ({ value: String(entity.id), label: entity.name })));
  let estimate = $derived((debt?.outstanding_principal ?? 0) + (debt?.accrued_interest ?? 0));

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function money(value) {
    return maskAmount(`${formatAmount(value)} ${debt?.currency ?? ''}`, debt?.currency);
  }

  $effect(() => {
    if (!open) return;
    crud.entities
      .getList()
      .then((rows) => {
        entities = rows;
        entityId = debt?.disbursement_entity_id ? String(debt.disbursement_entity_id) : '';
      })
      .catch(() => {});
    settledAt = today();
    amount = '';
    notes = '';
    error = '';
  });

  async function save() {
    if (!entityId) {
      error = t('debt.form.incomplete');
      return;
    }
    submitting = true;
    error = '';
    try {
      await debtApi.settle(debt.id, {
        settled_at: settledAt,
        entity_id: Number(entityId),
        amount: amount === '' ? null : Number(amount),
        notes: notes || null,
      });
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e?.message || t('debt.saveFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('debt.settle')} size="sm">
  <ModalForm>
    <p class="hint">
      {t('debt.payoff')}: {money(estimate)}
    </p>
    <FormField label={t('debt.settlementDate')} required>
      <input class="input" type="date" bind:value={settledAt} />
    </FormField>
    <FormField label={t('debt.cashEntity')} required>
      <Select bind:value={entityId} options={entityOptions} />
    </FormField>
    <FormField label={t('debt.paidAmount')}>
      <NumberInput bind:value={amount} min="0" step="0.01" placeholder={String(estimate.toFixed(2))} />
    </FormField>
    <FormField label={t('common.notes')}>
      <input class="input" type="text" bind:value={notes} />
    </FormField>
    <FormError message={error} />
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={save} disabled={submitting}>
        {submitting ? t('debt.saving') : t('debt.settle')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>
  .input {
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
</style>
