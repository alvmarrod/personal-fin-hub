<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, fee = null, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let name = $state('');

  $effect(() => {
    if (open) {
      name = fee ? fee.name : '';
      error = '';
    }
  });

  async function handleSubmit() {
    if (!name.trim()) {
      error = t('brokerFees.validation.name');
      return;
    }
    submitting = true;
    error = '';
    try {
      const payload = { name: name.trim() };
      if (fee) {
        await crud.brokerFeeDefinitions.update(fee.id, payload);
      } else {
        await crud.brokerFeeDefinitions.create(payload);
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

<Modal {open} {onclose} title={fee ? t('brokerFees.editTitle') : t('brokerFees.addTitle')} size="md">
  <ModalForm>
    <FormField label={t('brokerFees.nameLabel')} required>
      <TextInput bind:value={name} aria-label={t('brokerFees.nameLabel')} />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : fee ? t('common.save') : t('common.create')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

</style>