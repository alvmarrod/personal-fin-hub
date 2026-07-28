<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, onclose, onsuccess, exemption = null } = $props();

  let submitting = $state(false);
  let error = $state('');

  let exemptionType = $state('');
  let description = $state('');
  let exemptionAmount = $state('0');
  let exemptionRate = $state('100');
  let exemptionRateLimit = $state('');

  $effect(() => {
    if (exemption) {
      exemptionType = exemption.exemption_type || '';
      description = exemption.description || '';
      exemptionAmount = String(exemption.exemption_amount ?? 0);
      exemptionRate = String(exemption.exemption_rate ?? 100);
      exemptionRateLimit = exemption.exemption_rate_limit != null ? String(exemption.exemption_rate_limit) : '';
    }
  });

  async function handleSubmit() {
    if (!exemptionType) {
      error = 'Exemption type is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.fiscalExemptions.update(exemption.id, {
        exemption_type: exemptionType,
        description: description || null,
        exemption_amount: parseFloat(exemptionAmount) || 0,
        exemption_rate: parseFloat(exemptionRate) || 100,
        exemption_rate_limit: exemptionRateLimit ? parseFloat(exemptionRateLimit) : null,
      });
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.updateFailed') + ' fiscal exemption';
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('modals.editFiscalExemption')} size="md">
  <div class="form">
    <FormField label={t('modals.exemptionType')} required>
      <TextInput bind:value={exemptionType} placeholder="e.g. NISA, ISA, 401k" />
    </FormField>
    <FormField label={t('common.description')}>
      <TextInput bind:value={description} placeholder={t('modals.notesPlaceholder')} />
    </FormField>
    <div class="form-row">
      <FormField label={t('common.amount')}>
        <NumberInput bind:value={exemptionAmount} min="0" step="any" placeholder="e.g. 1200000" />
      </FormField>
      <FormField label={t('modals.rate')}>
        <NumberInput bind:value={exemptionRate} min="0" max="100" step="any" placeholder="e.g. 100" />
      </FormField>
    </div>
    <FormField label={t('modals.rateLimit')}>
      <NumberInput bind:value={exemptionRateLimit} min="0" step="any" placeholder="Optional upper limit" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : t('common.create')}
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
