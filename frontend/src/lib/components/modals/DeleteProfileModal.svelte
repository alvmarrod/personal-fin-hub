<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { deleteProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, profile = null } = $props();

  let typed = $state('');
  let submitting = $state(false);
  let error = $state('');

  let confirmWord = $derived(t('profiles.deleteWord'));
  let matches = $derived(typed === confirmWord);

  $effect(() => {
    if (open) {
      typed = '';
      error = '';
    }
  });

  async function handleConfirm() {
    if (!profile || !matches) return;
    submitting = true;
    error = '';
    try {
      await deleteProfile(profile.id);
      onclose?.();
    } catch (e) {
      if (e.status === 409) {
        error = t('profiles.lastProfile');
      } else {
        error = e.message || t('profiles.deleteFailed');
      }
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('profiles.deleteTitle')} size="sm">
  <ModalForm>
    <p class="form-desc">
      {t('profiles.deleteDesc', { name: profile ? profile.name : '' })}
    </p>
    <FormField label={t('profiles.deleteTypeToConfirm', { word: confirmWord })} required>
      <TextInput bind:value={typed} placeholder={confirmWord} />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="danger" onclick={handleConfirm} disabled={!matches || submitting}>
        {submitting ? t('common.deleting') : t('profiles.delete')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

  .form-desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.5;
  }

</style>
