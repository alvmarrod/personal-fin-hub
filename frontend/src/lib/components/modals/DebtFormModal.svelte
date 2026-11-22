<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';

  let { open = false, onclose, debt = null, onsaved } = $props();

  let submitting = $state(false);
  let error = $state('');
  let currencies = $state([]);
  let entities = $state([]);
  let counterparties = $state([]);

  let direction = $state('payable');
  let counterparty = $state('');
  let description = $state('');
  let currency = $state('EUR');
  let principal = $state('');
  let startDate = $state('');
  let annualRate = $state('');
  let termMonths = $state('');
  let maturityDate = $state('');
  let installmentMode = $state('manual');
  let installmentAmount = $state('');
  let principalPerInstallment = $state('');
  let dayCount = $state('monthly');
  let resetMode = $state('recalculate_installment');
  let reviewPeriod = $state('');
  let cashMode = $state('none');
  let cashEntity = $state('');
  let cashDate = $state('');
  let paymentEntity = $state('');
  let paymentPeriodicity = $state('');
  let firstPaymentDate = $state('');
  let notes = $state('');

  let editing = $derived(debt != null);

  const DAY_COUNTS = [
    { value: 'monthly', label: t('debt.daycount.monthly') },
    { value: 'actual_365', label: t('debt.daycount.actual365') },
    { value: 'actual_360', label: t('debt.daycount.actual360') },
    { value: 'thirty_360', label: t('debt.daycount.thirty360') },
  ];

  let modeOptions = $derived([
    { value: 'equal_payment', label: t('debt.mode.equalPayment') },
    { value: 'equal_principal', label: t('debt.mode.equalPrincipal') },
    { value: 'interest_only', label: t('debt.mode.interestOnly') },
    { value: 'manual', label: t('debt.mode.manual') },
  ]);

  let resetOptions = $derived([
    { value: 'recalculate_installment', label: t('debt.reset.recalculate') },
    { value: 'keep_installment', label: t('debt.reset.keep') },
  ]);

  let reviewOptions = $derived([
    { value: '', label: t('debt.reviewNone') },
    { value: '1', label: t('debt.review1') },
    { value: '3', label: t('debt.review3') },
    { value: '6', label: t('debt.review6') },
    { value: '12', label: t('debt.review12') },
  ]);

  let periodicityOptions = $derived([
    { value: '', label: t('debt.reviewNone') },
    { value: 'MONTHLY', label: t('debt.periodicity.monthly') },
    { value: 'QUARTERLY', label: t('debt.periodicity.quarterly') },
    { value: 'ANNUALLY', label: t('debt.periodicity.annually') },
    { value: 'WEEKLY', label: t('debt.periodicity.weekly') },
  ]);

  let currencyOptions = $derived(currencies.map((code) => ({ value: code, label: code })));
  let entityOptions = $derived(entities.map((entity) => ({ value: String(entity.id), label: entity.name })));

  function localDate() {
    return new Date().toISOString().slice(0, 10);
  }

  async function loadOptions() {
    try {
      [currencies, entities, counterparties] = await Promise.all([
        currenciesApi.getList(),
        crud.entities.getList(),
        debtApi.counterparties(),
      ]);
    } catch {
      // Options are optional; the form still submits.
    }
  }

  $effect(() => {
    if (!open) return;
    loadOptions();
    if (debt) {
      direction = debt.direction;
      counterparty = debt.counterparty_name;
      description = debt.description ?? '';
      currency = debt.currency;
      principal = String(debt.principal);
      startDate = debt.start_date;
      annualRate = String(debt.current_rate ?? 0);
      termMonths = debt.term_months ? String(debt.term_months) : '';
      maturityDate = debt.maturity_date ?? '';
      installmentMode = debt.installment_mode;
      installmentAmount = debt.installment_amount ? String(debt.installment_amount) : '';
      principalPerInstallment = debt.principal_per_installment ? String(debt.principal_per_installment) : '';
      dayCount = debt.day_count;
      resetMode = debt.rate_reset_mode;
      reviewPeriod = debt.review_period_months ? String(debt.review_period_months) : '';
      cashMode = debt.disbursement_mode;
      cashEntity = debt.disbursement_entity_id ? String(debt.disbursement_entity_id) : '';
      cashDate = debt.disbursement_date ?? '';
      paymentEntity = '';
      paymentPeriodicity = '';
      firstPaymentDate = '';
      notes = debt.notes ?? '';
    } else {
      direction = 'payable';
      counterparty = '';
      description = '';
      currency = 'EUR';
      principal = '';
      startDate = localDate();
      annualRate = '0';
      termMonths = '';
      maturityDate = '';
      installmentMode = 'manual';
      installmentAmount = '';
      principalPerInstallment = '';
      dayCount = 'monthly';
      resetMode = 'recalculate_installment';
      reviewPeriod = '';
      cashMode = 'none';
      cashEntity = '';
      cashDate = localDate();
      paymentEntity = '';
      paymentPeriodicity = '';
      firstPaymentDate = '';
      notes = '';
    }
    error = '';
  });

  function numberOrNull(value) {
    return value === '' || value === null ? null : Number(value);
  }

  function buildPayload() {
    return {
      direction,
      counterparty_name: counterparty.trim(),
      description: description || null,
      currency,
      principal: Number(principal),
      start_date: startDate,
      term_months: numberOrNull(termMonths),
      maturity_date: maturityDate || null,
      installment_mode: installmentMode,
      installment_amount: numberOrNull(installmentAmount),
      principal_per_installment: numberOrNull(principalPerInstallment),
      day_count: dayCount,
      rate_reset_mode: resetMode,
      review_period_months: numberOrNull(reviewPeriod),
      disbursement_mode: cashMode,
      disbursement_entity_id: cashMode === 'pocket' ? numberOrNull(cashEntity) : null,
      disbursement_date: cashMode === 'pocket' ? cashDate : null,
      payment_entity_id: paymentPeriodicity ? numberOrNull(paymentEntity) : null,
      payment_periodicity: paymentPeriodicity || null,
      first_payment_date: paymentPeriodicity ? firstPaymentDate || null : null,
      notes: notes || null,
    };
  }

  async function save() {
    if (!counterparty.trim() || !Number(principal) || !startDate) {
      error = t('debt.form.incomplete');
      return;
    }
    submitting = true;
    error = '';
    const payload = buildPayload();
    if (!editing) payload.annual_rate = Number(annualRate || 0);
    try {
      if (editing) {
        await debtApi.update(debt.id, payload);
      } else {
        await debtApi.create(payload);
      }
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e?.message || t('debt.saveFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={editing ? t('debt.editTitle') : t('debt.add')} size="md">
  <div class="form">
    <div class="grid">
      <FormField label={t('debt.colDirection')}>
        <Select bind:value={direction} options={[
          { value: 'payable', label: t('debt.iOwe') },
          { value: 'receivable', label: t('debt.owedToMe') },
        ]} />
      </FormField>
      <FormField label={t('debt.counterparty')} required>
        <input class="input" type="text" bind:value={counterparty} list="debt-counterparties" />
        <datalist id="debt-counterparties">
          {#each counterparties as name (name)}
            <option value={name}></option>
          {/each}
        </datalist>
      </FormField>
      <FormField label={t('common.currency')}>
        <Select bind:value={currency} options={currencyOptions} disabled={editing} />
      </FormField>
      <FormField label={t('debt.principal')} required>
        <NumberInput bind:value={principal} min="0" step="0.01" disabled={editing} />
      </FormField>
      <FormField label={t('debt.startDate')}>
        <input class="input" type="date" bind:value={startDate} disabled={editing} />
      </FormField>
      <FormField label={t('debt.annualRate')}>
        <NumberInput bind:value={annualRate} min="0" max="100" step="0.01" disabled={editing} />
      </FormField>
      <FormField label={t('debt.termMonths')}>
        <NumberInput bind:value={termMonths} min="1" step="1" />
      </FormField>
      <FormField label={t('debt.maturityDate')}>
        <input class="input" type="date" bind:value={maturityDate} />
      </FormField>
      <FormField label={t('debt.installmentMode')}>
        <Select bind:value={installmentMode} options={modeOptions} />
      </FormField>
      {#if installmentMode === 'equal_payment'}
        <FormField label={t('debt.installmentAmount')}>
          <NumberInput bind:value={installmentAmount} min="0" step="0.01" />
        </FormField>
      {:else if installmentMode === 'equal_principal'}
        <FormField label={t('debt.principalPerInstallment')}>
          <NumberInput bind:value={principalPerInstallment} min="0" step="0.01" />
        </FormField>
      {/if}
      <FormField label={t('debt.dayCount')}>
        <Select bind:value={dayCount} options={DAY_COUNTS} />
      </FormField>
      <FormField label={t('debt.resetMode')}>
        <Select bind:value={resetMode} options={resetOptions} />
      </FormField>
      <FormField label={t('debt.reviewPeriod')}>
        <Select bind:value={reviewPeriod} options={reviewOptions} />
      </FormField>
    </div>

    <fieldset class="section">
      <legend>{t('debt.cashMovement')}</legend>
      <div class="grid">
        <FormField label={t('debt.cashMode')}>
          <Select bind:value={cashMode} options={[
            { value: 'none', label: t('debt.cashModeNone') },
            { value: 'pocket', label: t('debt.cashModePocket') },
          ]} />
        </FormField>
        {#if cashMode === 'pocket'}
          <FormField label={t('debt.cashEntity')}>
            <Select bind:value={cashEntity} options={entityOptions} />
          </FormField>
          <FormField label={t('debt.cashDate')}>
            <input class="input" type="date" bind:value={cashDate} />
          </FormField>
        {/if}
      </div>
    </fieldset>

    <fieldset class="section">
      <legend>{t('debt.paymentPlan')}</legend>
      <div class="grid">
        <FormField label={t('debt.paymentPeriodicity')}>
          <Select bind:value={paymentPeriodicity} options={periodicityOptions} />
        </FormField>
        {#if paymentPeriodicity}
          <FormField label={t('debt.paymentEntity')}>
            <Select bind:value={paymentEntity} options={entityOptions} />
          </FormField>
          <FormField label={t('debt.firstPaymentDate')}>
            <input class="input" type="date" bind:value={firstPaymentDate} />
          </FormField>
        {/if}
      </div>
    </fieldset>

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
  .section {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    margin: 0;
  }
  .section legend {
    padding: 0 var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
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
  @media (max-width: 600px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
