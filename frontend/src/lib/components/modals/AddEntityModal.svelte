<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let name = $state('');
  let entityType = $state('BROKER');
  let country = $state('');
  let description = $state('');

  let typeOptions = $derived([
    { value: 'BROKER', label: t('modals.entityTypeBroker') },
    { value: 'BANK', label: t('modals.entityTypeBank') },
    { value: 'EMPLOYER', label: t('modals.entityTypeEmployer') },
    { value: 'EXCHANGE', label: t('modals.entityTypeExchange') },
    { value: 'OTHER', label: t('modals.entityTypeOther') },
  ]);

  async function handleSubmit() {
    if (!name) {
      error = t('modals.nameRequired');
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.entities.create({ name, entity_type: entityType, country: country || null, description: description || null });
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
    name = '';
    entityType = 'BROKER';
    country = '';
    description = '';
  }
</script>

<Modal {open} {onclose} title={t('modals.addEntity')} size="sm">
  <div class="form">
    <FormField label={t('common.name')} required>
      <TextInput bind:value={name} placeholder={t('modals.entityNamePlaceholder')} />
    </FormField>
    <FormField label={t('common.type')} required>
      <Select bind:value={entityType} options={typeOptions} />
    </FormField>
    <FormField label={t('modals.country')}>
      <TextInput bind:value={country} placeholder={t('modals.entityCountryPlaceholder')} />
    </FormField>
    <FormField label={t('common.description')}>
      <TextInput bind:value={description} placeholder={t('modals.notesPlaceholder')} />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.creating') : t('common.create')}
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
