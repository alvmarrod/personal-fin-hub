<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { renameProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';

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
  <div class="form">
    <FormField label={t('common.name')} required>
      <TextInput bind:value={name} placeholder={t('common.name')} />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : t('profiles.rename')}
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
