<script>
  let { value = $bindable(''), placeholder = '', type = 'text', disabled = false, ...rest } = $props();

  function parsePastedDate(text) {
    text = text.trim();
    if (!text) return null;

    // Already ISO format: 2025-06-11
    const iso = /^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})$/.exec(text);
    if (iso) {
      const [, y, m, d] = iso;
      return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
    }

    // DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (European)
    const eu = /^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/.exec(text);
    if (eu) {
      const [, d, m, y] = eu;
      const day = parseInt(d), month = parseInt(m);
      if (day < 1 || day > 31 || month < 1 || month > 12) return null;
      return `${y}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }

    // YYYYMMDD (compact)
    const compact = /^(\d{4})(\d{2})(\d{2})$/.exec(text);
    if (compact) {
      const [, y, m, d] = compact;
      return `${y}-${m}-${d}`;
    }

    return null;
  }

  function handlePaste(e) {
    if (type !== 'date') return;

    const pasted = e.clipboardData?.getData('text');
    if (!pasted) return;

    const parsed = parsePastedDate(pasted);
    if (parsed) {
      e.preventDefault();
      value = parsed;
    }
  }
</script>

<input {type} {placeholder} {disabled} bind:value class="text-input" onpaste={handlePaste} {...rest} />

<style>
  .text-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font-family: inherit;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    outline: none;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    height: 40px;
  }

  .text-input:focus {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-light);
  }

  .text-input:disabled {
    background: var(--color-surface-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  .text-input::placeholder {
    color: var(--color-text-muted);
  }
</style>
