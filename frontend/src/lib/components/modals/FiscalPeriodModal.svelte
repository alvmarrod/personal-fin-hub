<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Select from '../Select.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, period = null, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let ruleKey = $state('default');
  let startDate = $state('');
  let endDate = $state('');

  const ruleOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  $effect(() => {
    if (open) {
      ruleKey = period ? period.rule_key : 'default';
      startDate = period ? period.start_date : '';
      endDate = period ? (period.end_date || '') : '';
      error = '';
    }
  });

  async function handleSubmit() {
    if (!startDate) {
      error = t('fiscalRules.startDateRequired');
      return;
    }
    submitting = true;
    error = '';
    try {
      const payload = {
        rule_key: ruleKey,
        start_date: startDate,
        end_date: endDate || null,
      };
      if (period) {
        await crud.fiscalPeriods.update(period.id, payload);
      } else {
        await crud.fiscalPeriods.create(payload);
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

<Modal {open} {onclose} title={period ? t('fiscalRules.editTitle') : t('fiscalRules.addTitle')} size="md">
  <div class="form">
    <FormField label={t('fiscalRules.ruleLabel')} required>
      <Select bind:value={ruleKey} options={ruleOptions} />
    </FormField>
    <div class="form-row">
      <FormField label={t('fiscalRules.startDate')} required>
        <TextInput bind:value={startDate} type="date" />
      </FormField>
      <FormField label={t('fiscalRules.endDate')}>
        <TextInput bind:value={endDate} type="date" placeholder={t('fiscalRules.openEnded')} />
      </FormField>
    </div>
    <p class="form-hint">{t('fiscalRules.openEndedHint')}</p>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : period ? t('common.save') : t('common.create')}
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

  .form-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0;
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
