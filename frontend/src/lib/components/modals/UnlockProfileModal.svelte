<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { unlockProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';
  import ModalForm from '$lib/components/ModalForm.svelte';

  let { open = false, onclose, profile = null } = $props();

  let password = $state('');
  let submitting = $state(false);
  let error = $state('');

  let title = $derived(profile ? t('profiles.unlockTitle', { name: profile.name }) : '');

  async function handleSubmit() {
    if (!profile) return;
    submitting = true;
    error = '';
    try {
      await unlockProfile(profile, password);
      password = '';
      onclose?.();
    } catch (e) {
      if (e.status === 401) {
        error = t('profiles.invalidPassword');
      } else if (e.status === 404) {
        error = e.message || t('common.noData');
      } else {
        error = e.message || t('modals.createFailed');
      }
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} {title} size="sm">
  <ModalForm>
    <p class="form-desc">{t('profiles.unlockDesc')}</p>
    <FormField label={t('profiles.password')} required>
      <TextInput bind:value={password} type="password" />
    </FormField>
    {#if error}
      <FormError message={error} />
    {/if}
    <FormActions>
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting || !password}>
        {submitting ? t('profiles.unlock') : t('profiles.unlock')}
      </Button>
    </FormActions>
  </ModalForm>
</Modal>

<style>

  .form-desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
    line-height: 1.5;
  }

</style>
