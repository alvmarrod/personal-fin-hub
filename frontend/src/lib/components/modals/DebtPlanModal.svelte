<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';

  let { open = false, onclose, debt = null, onsaved } = $props();

  let submitting = $state(false);
  let error = $state('');
  let text = $state('');

  $effect(() => {
    if (!open) return;
    error = '';
    if (debt) {
      debtApi
        .plan(debt.id)
        .then((rows) => {
          text = (rows ?? [])
            .map((row) =>
              [
                row.due_date,
                row.payment_amount,
                row.principal_amount,
                row.interest_amount,
                row.fees_amount,
                row.insurance_amount,
                row.other_amount,
              ].join(', '),
            )
            .join('\n');
        })
        .catch(() => {
          text = '';
        });
    } else {
      text = '';
    }
  });

  function parse() {
    const entries = [];
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const parts = trimmed.split(/[,;\t]/).map((part) => part.trim());
      if (parts.length < 4) throw new Error(trimmed);
      const [due, payment, principal, interest, fees = '0', insurance = '0', other = '0'] = parts;
      entries.push({
        due_date: due,
        payment_amount: Number(payment),
        principal_amount: Number(principal),
        interest_amount: Number(interest),
        fees_amount: Number(fees),
        insurance_amount: Number(insurance),
        other_amount: Number(other),
      });
    }
    return entries;
  }

  async function save() {
    submitting = true;
    error = '';
    try {
      const entries = parse();
      if (entries.length === 0) throw new Error('');
      await debtApi.importPlan(debt.id, {
        replace_from: entries[0].due_date,
        entries,
      });
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e?.message ? t('debt.planParseError', { line: e.message }) : t('debt.planParseError', { line: '' });
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} {onclose} title={t('debt.planTitle')} size="md">
  <div class="form">
    <p class="hint">{t('debt.planHint')}</p>
    <textarea class="area" rows="10" bind:value={text} spellcheck="false"></textarea>
    {#if error}<p class="error">{error}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
      <Button variant="primary" onclick={save} disabled={submitting}>
        {submitting ? t('debt.saving') : t('common.save')}
      </Button>
    </div>
  </div>
</Modal>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .hint {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .area {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-primary);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    resize: vertical;
  }
  .error {
    margin: 0;
    font-size: var(--font-size-sm);
    color: var(--color-danger);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
