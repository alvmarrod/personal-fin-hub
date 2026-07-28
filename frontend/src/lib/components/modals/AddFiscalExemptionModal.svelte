<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';

  let { open = false, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let exemptionType = $state('');
  let description = $state('');
  let exemptionAmount = $state('0');
  let exemptionRate = $state('100');
  let exemptionRateLimit = $state('');

  async function handleSubmit() {
    if (!exemptionType) {
      error = 'Exemption type is required';
      return;
    }
    submitting = true;
    error = '';
    try {
      await crud.fiscalExemptions.create({
        exemption_type: exemptionType,
        description: description || null,
        exemption_amount: parseFloat(exemptionAmount) || 0,
        exemption_rate: parseFloat(exemptionRate) || 100,
        exemption_rate_limit: exemptionRateLimit ? parseFloat(exemptionRateLimit) : null,
      });
      reset();
      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || 'Failed to create fiscal exemption';
    } finally {
      submitting = false;
    }
  }

  function reset() {
    exemptionType = '';
    description = '';
    exemptionAmount = '0';
    exemptionRate = '100';
    exemptionRateLimit = '';
  }

  $effect(() => {
    if (open) reset();
  });
</script>

<Modal {open} {onclose} title="Add Fiscal Exemption" size="md">
  <div class="form">
    <FormField label="Exemption Type" required>
      <TextInput bind:value={exemptionType} placeholder="e.g. NISA, ISA, 401k" />
    </FormField>
    <FormField label="Description">
      <TextInput bind:value={description} placeholder="Optional description" />
    </FormField>
    <div class="form-row">
      <FormField label="Exemption Amount">
        <NumberInput bind:value={exemptionAmount} min="0" step="any" placeholder="e.g. 1200000" />
      </FormField>
      <FormField label="Exemption Rate (%)">
        <NumberInput bind:value={exemptionRate} min="0" max="100" step="any" placeholder="e.g. 100" />
      </FormField>
    </div>
    <FormField label="Rate Limit">
      <NumberInput bind:value={exemptionRateLimit} min="0" step="any" placeholder="Optional upper limit" />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>Cancel</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? 'Creating...' : 'Create'}
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

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
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
