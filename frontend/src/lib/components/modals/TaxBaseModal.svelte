<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import TextInput from '../TextInput.svelte';
  import Select from '../Select.svelte';
  import Button from '../Button.svelte';
  import { crud } from '../../api/analytics';
  import { t } from '$lib/i18n/index.svelte';

  let { open = false, base = null, onclose, onsuccess } = $props();

  const CATEGORIES = ['capital_gains', 'dividends', 'interest'];

  let submitting = $state(false);
  let error = $state('');

  let name = $state('');
  let rulesetKey = $state('spain');
  let computation = $state('progressive');
  let categories = $state(['capital_gains']);
  let flatRate = $state('');
  let brackets = $state([{ from: '', to: '', rate: '' }]);
  let yearStart = $state('');

  const rulesetOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  const computationOptions = [
    { value: 'progressive', label: t('taxBases.computation.progressive') },
    { value: 'flat', label: t('taxBases.computation.flat') },
  ];

  function parseOptionalNumber(value) {
    return value.trim() === '' ? null : parseFloat(value);
  }

  function validateBracketRow(row) {
    const from = parseFloat(row.from);
    const rate = parseFloat(row.rate);
    if (isNaN(from) || isNaN(rate)) return false;
    if (rate < 0 || rate > 1) return false;
    if (row.to.trim() !== '' && isNaN(parseFloat(row.to))) return false;
    return true;
  }

  function toggleCategory(category) {
    if (categories.includes(category)) {
      categories = categories.filter((c) => c !== category);
    } else {
      categories = [...categories, category];
    }
  }

  function addBracket() {
    brackets = [...brackets, { from: '', to: '', rate: '' }];
  }

  function removeBracket(index) {
    brackets = brackets.filter((_, i) => i !== index);
  }

  $effect(() => {
    if (open) {
      name = base ? base.name : '';
      rulesetKey = base ? base.ruleset_key : 'spain';
      computation = base ? base.computation : 'progressive';
      categories = base ? [...base.categories] : ['capital_gains'];
      flatRate = base && base.flat_rate != null ? String(base.flat_rate) : '';
      brackets = base && base.rates.length > 0
        ? base.rates.map((r) => ({
            from: String(r.from_amount),
            to: r.to_amount != null ? String(r.to_amount) : '',
            rate: String(r.rate),
          }))
        : [{ from: '', to: '', rate: '' }];
      yearStart = base && base.year_start != null ? String(base.year_start) : '';
      error = '';
    }
  });

  async function handleSubmit() {
    if (!name.trim()) {
      error = t('taxBases.validation.name');
      return;
    }
    if (categories.length === 0) {
      error = t('taxBases.validation.category');
      return;
    }
    if (computation === 'flat') {
      const parsedFlat = parseFloat(flatRate);
      if (isNaN(parsedFlat) || parsedFlat < 0 || parsedFlat > 1) {
        error = t('taxBases.validation.flatRate');
        return;
      }
    } else {
      if (brackets.length === 0) {
        error = t('taxBases.validation.noBrackets');
        return;
      }
      if (!brackets.some(validateBracketRow)) {
        error = t('taxBases.validation.bracket');
        return;
      }
    }
    submitting = true;
    error = '';
    try {
      const payload = {
        ruleset_key: rulesetKey,
        name: name.trim(),
        computation,
        flat_rate: computation === 'flat' ? parseFloat(flatRate) : null,
        year_start: yearStart ? parseInt(yearStart, 10) : null,
        categories: [...categories],
        rates: computation === 'flat'
          ? []
          : brackets
              .filter(validateBracketRow)
              .map((b) => ({
                from_amount: parseFloat(b.from),
                to_amount: parseOptionalNumber(b.to),
                rate: parseFloat(b.rate),
              })),
      };
      if (base) {
        await crud.taxBases.update(base.id, payload);
      } else {
        await crud.taxBases.create(payload);
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

<Modal {open} {onclose} title={base ? t('taxBases.editTitle') : t('taxBases.addTitle')} size="md">
  <div class="form">
    <FormField label={t('taxBases.nameLabel')} required>
      <TextInput bind:value={name} aria-label={t('taxBases.nameLabel')} />
    </FormField>
    <div class="form-row">
      <FormField label={t('taxBases.rulesetLabel')} required>
        <Select bind:value={rulesetKey} options={rulesetOptions} aria-label={t('taxBases.rulesetLabel')} />
      </FormField>
      <FormField label={t('taxBases.computationLabel')} required>
        <Select bind:value={computation} options={computationOptions} aria-label={t('taxBases.computationLabel')} />
      </FormField>
    </div>
    <FormField label={t('taxBases.categoriesLabel')} required>
      <div class="chip-list">
        {#each CATEGORIES as category}
          <button
            type="button"
            class="chip"
            class:active={categories.includes(category)}
            aria-pressed={categories.includes(category)}
            onclick={() => toggleCategory(category)}
          >
            {t(`taxBases.category.${category}`)}
          </button>
        {/each}
      </div>
    </FormField>
    {#if computation === 'flat'}
      <FormField label={t('taxBases.flatRate')} required>
        <TextInput bind:value={flatRate} type="number" step="0.0001" min="0" max="1" aria-label={t('taxBases.flatRate')} />
      </FormField>
    {:else}
      <FormField label={t('taxBases.brackets')} required>
        {#each brackets as bracket, index (index)}
          <div class="bracket-row">
            <TextInput
              bind:value={bracket.from}
              type="number"
              step="0.01"
              min="0"
              placeholder="0"
              aria-label={t(`taxBases.bracketFrom`)}
            />
            <TextInput
              bind:value={bracket.to}
              type="number"
              step="0.01"
              min="0"
              placeholder={t('taxBases.bracketToOptional')}
              aria-label={t('taxBases.bracketTo')}
            />
            <TextInput
              bind:value={bracket.rate}
              type="number"
              step="0.0001"
              min="0"
              max="1"
              placeholder="0.19"
              aria-label={t('taxBases.bracketRate')}
            />
            {#if brackets.length > 1}
              <Button variant="ghost" size="sm" onclick={() => removeBracket(index)} aria-label={t('taxBases.bracketRemove')}>
                ×
              </Button>
            {/if}
          </div>
        {/each}
        <Button variant="outline" size="sm" onclick={addBracket}>{t('taxBases.bracketAdd')}</Button>
      </FormField>
    {/if}
    <FormField label={t('taxBases.yearStart')} tooltip={t('taxBases.yearStartHint')}>
      <TextInput bind:value={yearStart} type="number" min="2000" placeholder={t('taxBases.allYears')} aria-label={t('taxBases.yearStart')} />
    </FormField>
    {#if error}
      <p class="form-error">{error}</p>
    {/if}
    <div class="form-actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
        {submitting ? t('common.saving') : base ? t('common.save') : t('common.create')}
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

  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .chip {
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    transition: border-color var(--transition-fast), background var(--transition-fast);
  }

  .chip:hover {
    border-color: var(--color-primary);
  }

  .chip.active {
    border-color: var(--color-primary);
    background: var(--color-primary-light, rgba(59, 130, 246, 0.08));
  }

  .bracket-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr auto;
    gap: var(--space-2);
    align-items: center;
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