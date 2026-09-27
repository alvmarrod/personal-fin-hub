<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Select from '../Select.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, definition = null, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  let name = $state('');
  let slug = $state('');
  let slugTouched = $state(false);
  let rulesetKey = $state('');
  let rate = $state('');
  let yearStart = $state('');

  const rulesetOptions = [
    { value: '', label: t('taxDefinitions.rulesetGeneric') },
    ...['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
      value: key,
      label: t(`fiscalRules.rule.${key}`),
    })),
  ];

  function slugify(value) {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function handleNameInput() {
    if (!slugTouched) {
      slug = slugify(name);
    }
  }

  $effect(() => {
    if (open) {
      name = definition ? definition.name : '';
      slug = definition ? definition.slug : '';
      slugTouched = Boolean(definition);
      rulesetKey = definition && definition.ruleset_key ? definition.ruleset_key : '';
      rate = definition && definition.rate != null ? String(definition.rate) : '';
      yearStart = definition && definition.year_start != null ? String(definition.year_start) : '';
      error = '';
    }
  });

  async function handleSubmit() {
    if (!name.trim()) {
      error = t('taxDefinitions.validation.name');
      return;
    }
    const slugValue = slugify(slug);
    if (!slugValue) {
      error = t('taxDefinitions.validation.slug');
      return;
    }
    const parsedRate = rate.trim() === '' ? null : parseFloat(rate);
    if (parsedRate != null && (isNaN(parsedRate) || parsedRate < 0 || parsedRate > 1)) {
      error = t('taxDefinitions.validation.rateRange');
      return;
    }
    submitting = true;
    error = '';
    try {
      const payload = {
        slug: slugValue,
        ruleset_key: rulesetKey === '' ? null : rulesetKey,
        name: name.trim(),
        rate: parsedRate,
        year_start: yearStart ? parseInt(yearStart, 10) : null,
      };
      if (definition) {
        await crud.taxDefinitions.update(definition.id, payload);
      } else {
        await crud.taxDefinitions.create(payload);
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

<Modal {open} {onclose} title={definition ? t('taxDefinitions.editTitle') : t('taxDefinitions.addTitle')} size="md">
  <div class="form">
    <div class="form-row">
      <FormField label={t('taxDefinitions.nameLabel')} required>
        <TextInput bind:value={name} oninput={handleNameInput} aria-label={t('taxDefinitions.nameLabel')} />
      </FormField>
      <FormField label={t('taxDefinitions.rulesetLabel')}>
        <Select bind:value={rulesetKey} options={rulesetOptions} aria-label={t('taxDefinitions.rulesetLabel')} />
      </FormField>
    </div>
    <div class="form-row">
      <FormField label={t('taxDefinitions.slugLabel')} required>
        <TextInput
          bind:value={slug}
          oninput={() => { slugTouched = true; }}
          aria-label={t('taxDefinitions.slugLabel')}
        />
      </FormField>
      <FormField label={t('taxDefinitions.yearStart')}>
        <TextInput bind:value={yearStart} type="number" min="2000" placeholder={t('taxDefinitions.allYears')} aria-label={t('taxDefinitions.yearStart')} />
      </FormField>
    </div>
    <FormField label={t('taxDefinitions.rateLabel')}>
      <TextInput bind:value={rate} type="number" step="0.0001" min="0" max="1" placeholder="0.002" aria-label={t('taxDefinitions.rateLabel')} />
      <p class="form-hint">{t('taxDefinitions.rateOptional')}</p>
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : definition ? t('common.save') : t('common.create')}
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

  .form-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: var(--space-1) 0 0 0;
  }

  .form-error {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
  }
</style>