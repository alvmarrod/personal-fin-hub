<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';

  let { open = false, onclose, onsuccess, entity = null } = $props();

  let submitting = $state(false);
  let error = $state('');

  let name = $state('');
  let entityType = $state('BROKER');
  let country = $state('');
  let description = $state('');

  let typeOptions = [
    { value: 'BROKER', label: 'Broker' },
    { value: 'BANK', label: 'Bank' },
    { value: 'EMPLOYER', label: 'Employer' },
    { value: 'EXCHANGE', label: 'Exchange' },
    { value: 'OTHER', label: 'Other' },
  ];

  $effect(() => {
    if (entity) {
      name = entity.name;
      entityType = entity.entity_type;
      country = entity.country || '';
      description = entity.description || '';
    }
  });

  async function handleSubmit() {
    if (!name) {
      error = 'Name is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.entities.update(entity.id, { name, entity_type: entityType, country: country || null, description: description || null });
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to update entity';
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title="Edit Entity" size="sm">
  <div class="form">
    <FormField label="Name" required>
      <TextInput bind:value={name} placeholder="e.g. Interactive Brokers" />
    </FormField>
    <FormField label="Type" required>
      <Select bind:value={entityType} options={typeOptions} />
    </FormField>
    <FormField label="Country">
      <TextInput bind:value={country} placeholder="e.g. US" />
    </FormField>
    <FormField label="Description">
      <TextInput bind:value={description} placeholder="Optional notes" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? 'Saving...' : 'Save Changes'}
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
