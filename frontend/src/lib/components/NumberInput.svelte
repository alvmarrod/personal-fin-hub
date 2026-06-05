<script>
  let { value = $bindable(''), placeholder = '', min, max, step, disabled = false, ...rest } = $props();
</script>

<input type="number" {placeholder} {min} {max} {step} {disabled} bind:value class="number-input" {...rest} />

<style>
  .number-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    outline: none;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    height: 40px;
    -moz-appearance: textfield;
  }

  .number-input::-webkit-outer-spin-button,
  .number-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .number-input:focus {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-light);
  }

  .number-input:disabled {
    background: var(--color-surface-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
</style>
