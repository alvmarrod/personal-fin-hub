<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { currenciesApi } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let code = $state('');

  async function handleSubmit() {
    if (!code) {
      error = t('modals.codeRequired');
      return;
    }
    submitting = true;
    error = '';
    try {
      await currenciesApi.create(code.toUpperCase());
      onsuccess?.();
      reset();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.createFailed');
    } finally {
      submitting = false;
    }
  }

  function reset() {
    code = '';
  }
</script>

<Modal {open} {onclose} title={t('modals.addCurrency')} size="sm">
  <ModalForm>
    <FormField label={t('modals.code')} required>
      <TextInput bind:value={code} placeholder="e.g. EUR" style="text-transform:uppercase" />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.creating') : t('common.create')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

</style>
