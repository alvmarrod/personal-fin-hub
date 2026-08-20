<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Select from '../Select.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, rate = null, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let rulesetKey = $state('spain');
  let category = $state('capital_gains');
  let fromAmount = $state('0');
  let toAmount = $state('');
  let rateValue = $state('');
  let yearStart = $state('');

  const rulesetOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  const categoryOptions = [
    { value: 'capital_gains', label: t('taxRates.category.capitalGains') },
    { value: 'dividends', label: t('taxRates.category.dividends') },
    { value: 'other', label: t('taxRates.category.other') },
  ];

  $effect(() => {
    if (open) {
      rulesetKey = rate ? rate.ruleset_key : 'spain';
      category = rate ? rate.category : 'capital_gains';
      fromAmount = rate ? String(rate.from_amount) : '0';
      toAmount = rate ? (rate.to_amount != null ? String(rate.to_amount) : '') : '';
      rateValue = rate ? String(rate.rate) : '';
      yearStart = rate ? (rate.year_start != null ? String(rate.year_start) : '') : '';
      error = '';
    }
  });

  async function handleSubmit() {
    const parsedFrom = parseFloat(fromAmount);
    const parsedRate = parseFloat(rateValue);
    if (isNaN(parsedFrom) || isNaN(parsedRate)) {
      error = t('taxRates.validation.numeric');
      return;
    }
    if (parsedRate < 0 || parsedRate > 1) {
      error = t('taxRates.validation.rateRange');
      return;
    }
    submitting = true;
    error = '';
    try {
      const payload = {
        ruleset_key: rulesetKey,
        category,
        from_amount: parsedFrom,
        to_amount: toAmount ? parseFloat(toAmount) : null,
        rate: parsedRate,
        year_start: yearStart ? parseInt(yearStart, 10) : null,
      };
      if (rate) {
        await crud.taxRates.update(rate.id, payload);
      } else {
        await crud.taxRates.create(payload);
      }
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.createFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={rate ? t('taxRates.editTitle') : t('taxRates.addTitle')} size="md">
  <div class="form">
    <FormField label={t('taxRates.rulesetLabel')} required>
      <Select bind:value={rulesetKey} options={rulesetOptions} />
    </FormField>
    <FormField label={t('taxRates.categoryLabel')} required>
      <Select bind:value={category} options={categoryOptions} />
    </FormField>
    <div class="form-row">
      <FormField label={t('taxRates.fromAmount')} required>
        <TextInput bind:value={fromAmount} type="number" step="0.01" />
      </FormField>
      <FormField label={t('taxRates.toAmount')}>
        <TextInput bind:value={toAmount} type="number" step="0.01" placeholder={t('taxRates.unlimited')} />
      </FormField>
    </div>
    <FormField label={t('taxRates.rateLabel')} required>
      <TextInput bind:value={rateValue} type="number" step="0.0001" min="0" max="1" />
    </FormField>
    <FormField label={t('taxRates.yearStart')}>
      <TextInput bind:value={yearStart} type="number" min="2000" placeholder={t('taxRates.allYears')} />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : rate ? t('common.save') : t('common.create')}
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
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
  }
</style>
