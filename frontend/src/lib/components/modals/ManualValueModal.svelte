<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, onsuccess, assetId = null, existing = null } = $props();

  let value = $state('');
  let effectiveDate = $state(today());
  let notes = $state('');
  let submitting = $state(false);
  let error = $state('');

  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  $effect(() => {
    if (open) {
      value = existing ? String(existing.value) : '';
      effectiveDate = existing ? existing.effective_date : today();
      notes = existing?.notes || '';
      error = '';
    }
  });

  async function handleSubmit() {
    if (!value) {
      error = t('modals.valueRequired');
      return;
    }
    submitting = true;
    error = '';
    try {
      if (existing && effectiveDate !== existing.effective_date) {
        await crud.portfolioAssets.deleteManualValue(assetId, existing.id);
      }
      await crud.portfolioAssets.createManualValue(assetId, {
        value: parseFloat(value),
        effective_date: effectiveDate,
        notes: notes || null,
      });
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.updateFailed');
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={existing ? t('modals.editValuation') : t('modals.addValuation')} size="sm">
  <ModalForm>
    <FormField label={t('modals.value')}>
      <NumberInput bind:value={value} min="0" step="any" placeholder="e.g. 10000" />
    </FormField>
    <FormField label={t('modals.effectiveDate')}>
      <TextInput type="date" bind:value={effectiveDate} />
    </FormField>
    <FormField label={t('common.notes')}>
      <TextInput bind:value={notes} placeholder={t('modals.notesPlaceholder')} />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : t('common.save')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

</style>
