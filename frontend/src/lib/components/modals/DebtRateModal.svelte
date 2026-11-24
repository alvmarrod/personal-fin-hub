<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormField from '../FormField.svelte';
  import NumberInput from '../NumberInput.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, debt = null, onsaved } = $props();

  let submitting = $state(false);
  let error = $state('');
  let effectiveFrom = $state('');
  let annualRate = $state('');

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  $effect(() => {
    if (!open) return;
    effectiveFrom = today();
    annualRate = debt ? String(debt.current_rate) : '0';
    error = '';
  });

  async function save() {
    submitting = true;
    error = '';
    try {
      await debtApi.addRate(debt.id, {
        effective_from: effectiveFrom,
        annual_rate: Number(annualRate),
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

<Modal {open} {onclose} title={t('debt.changeRate')} size="sm">
  <ModalForm>
    <FormField label={t('debt.rateDate')} required>
      <input class="input" type="date" bind:value={effectiveFrom} />
    </FormField>
    <FormField label={t('debt.annualRate')} required>
      <NumberInput bind:value={annualRate} min="0" max="100" step="0.01" />
    </FormField>
    <FormError message={error} />
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={save} disabled={submitting}>
        {submitting ? t('debt.saving') : t('common.save')}
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
</style>
