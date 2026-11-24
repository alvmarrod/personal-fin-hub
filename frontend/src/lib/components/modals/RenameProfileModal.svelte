<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { renameProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, profile = null } = $props();

  let name = $state('');
  let submitting = $state(false);
  let error = $state('');

  $effect(() => {
    if (open && profile) {
      name = profile.name;
      error = '';
    }
  });

  async function handleSubmit() {
    if (!profile) return;
    if (!name.trim()) {
      error = t('profiles.required');
      return;
    }
    submitting = true;
    error = '';
    try {
      await renameProfile(profile.id, name.trim());
      onclose?.();
    } catch (e) {
      if (e.status === 409) {
        error = t('profiles.nameTaken');
      } else {
        error = e.message || t('modals.updateFailed');
      }
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('profiles.renameTitle')} size="sm">
  <ModalForm>
    <FormField label={t('common.name')} required>
      <TextInput bind:value={name} placeholder={t('common.name')} />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : t('profiles.rename')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

</style>
