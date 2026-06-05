<script>
  let { value = $bindable(''), placeholder = '', type = 'text', disabled = false, ...rest } = $props();
</script>

<input {type} {placeholder} {disabled} bind:value class="text-input" {...rest} />

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
