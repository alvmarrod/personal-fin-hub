<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { createProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, onclose } = $props();

  let name = $state('');
  let password = $state('');
  let submitting = $state(false);
  let error = $state('');

  async function handleSubmit() {
    if (!name.trim()) {
      error = t('profiles.required');
      return;
    }
    submitting = true;
    error = '';
    try {
      await createProfile(name.trim(), password || null);
      reset();
      onclose?.();
    } catch (e) {
      if (e.status === 409) {
        error = t('profiles.nameTaken');
      } else {
        error = e.message || t('modals.createFailed');
      }
    } finally {
      submitting = false;
    }
  }

  function reset() {
    name = '';
    password = '';
    error = '';
  }
</script>

<Modal {open} {onclose} title={t('profiles.createTitle')} size="sm">
  <div class="form">
    <p class="form-desc">{t('profiles.createDesc')}</p>
    <FormField label={t('common.name')} required>
      <TextInput bind:value={name} placeholder={t('common.name')} />
    </FormField>
    <FormField label={t('profiles.passwordOptional')}>
      <TextInput bind:value={password} type="password" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('profiles.creating') : t('profiles.create')}
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

  .form-desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
    line-height: 1.5;
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
