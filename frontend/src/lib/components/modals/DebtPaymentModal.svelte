<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import { entities as entityApi } from '$lib/api/analytics.js';
  import { formatAmount, formatPercent, maskAmount } from '$lib/utils/format.svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import NumberInput from '../NumberInput.svelte';

  let { open = false, onclose, debt = null, onsaved } = $props();

  let submitting = $state(false);
  let error = $state('');
  let entities = $state([]);
  let paidAt = $state('');
  let entityId = $state('');
  let amount = $state('');
  let principalOnly = $state(false);
  let advanced = $state(false);
  let principalAmount = $state('');
  let interestAmount = $state('');
  let fees = $state('0');
  let insurance = $state('0');
  let other = $state('0');
  let notes = $state('');

  let entityOptions = $derived(entities.map((entity) => ({ value: String(entity.id), label: entity.name })));

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function money(value) {
    return maskAmount(`${formatAmount(value)} ${debt?.currency ?? ''}`, debt?.currency);
  }

  async function loadEntities() {
    try {
      entities = await crud.entities.getList();
    } catch {
      // The form still renders.
    }
  }

  $effect(() => {
    if (!open) return;
    loadEntities();
    paidAt = today();
    entityId = debt?.disbursement_entity_id ? String(debt.disbursement_entity_id) : '';
    amount = '';
    principalOnly = false;
    advanced = false;
    principalAmount = '';
    interestAmount = '';
    fees = '0';
    insurance = '0';
    other = '0';
    notes = '';
    error = '';
  });

  function number(value) {
    return value === '' ? 0 : Number(value);
  }

  async function save() {
    if (!entityId || !Number(amount)) {
      error = t('debt.form.incomplete');
      return;
    }
    if (advanced) {
      const total =
        number(principalAmount) + number(interestAmount) + number(fees) + number(insurance) + number(other);
      if (Math.abs(total - Number(amount)) > 0.01) {
        error = t('debt.splitMismatch');
        return;
      }
    }
    submitting = true;
    error = '';
    const payload = {
      paid_at: paidAt,
      entity_id: Number(entityId),
      amount: Number(amount),
      fees_amount: number(fees),
      insurance_amount: number(insurance),
      other_amount: number(other),
      principal_only: principalOnly,
      kind: 'regular',
      notes: notes || null,
    };
    if (advanced) {
      payload.principal_amount = number(principalAmount);
      payload.interest_amount = number(interestAmount);
    }
    try {
      await debtApi.pay(debt.id, payload);
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e?.message || t('debt.saveFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('debt.addPayment')} size="sm">
  <div class="form">
    {#if debt}
      <p class="hint">
        {t('debt.outstanding')}: {money(debt.outstanding_principal)} ·
        {t('debt.accrued')}: {money(debt.accrued_interest)}
        {#if !privacyHidden()}<span class="muted">({formatPercent(debt.current_rate)})</span>{/if}
      </p>
    {/if}
    <FormField label={t('debt.paymentDate')} required>
      <input class="input" type="date" bind:value={paidAt} />
    </FormField>
    <FormField label={t('debt.cashEntity')} required>
      <Select bind:value={entityId} options={entityOptions} />
    </FormField>
    <FormField label={t('common.amount')} required>
      <NumberInput bind:value={amount} min="0" step="0.01" />
    </FormField>
    <label class="check">
      <input type="checkbox" bind:checked={principalOnly} />
      {t('debt.principalOnly')}
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={advanced} />
      {t('debt.enterSplit')}
    </label>
    {#if advanced}
      <div class="grid">
        <FormField label={t('debt.principalPart')}>
          <NumberInput bind:value={principalAmount} min="0" step="0.01" />
        </FormField>
        <FormField label={t('debt.interestPart')}>
          <NumberInput bind:value={interestAmount} min="0" step="0.01" />
        </FormField>
        <FormField label={t('debt.fees')}>
          <NumberInput bind:value={fees} min="0" step="0.01" />
        </FormField>
        <FormField label={t('debt.insurance')}>
          <NumberInput bind:value={insurance} min="0" step="0.01" />
        </FormField>
        <FormField label={t('debt.other')}>
          <NumberInput bind:value={other} min="0" step="0.01" />
        </FormField>
      </div>
    {/if}
    <FormField label={t('common.notes')}>
      <input class="input" type="text" bind:value={notes} />
    </FormField>
    {#if error}<p class="error">{error}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={save} disabled={submitting}>
        {submitting ? t('debt.saving') : t('common.save')}
      </Button>
    </div>
  </div>
</Modal>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }
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
  .muted {
    color: var(--color-text-muted);
  }
  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }
  .error {
    margin: 0;
    font-size: var(--font-size-sm);
    color: var(--color-danger);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
