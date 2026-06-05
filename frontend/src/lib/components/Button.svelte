<script>
  let {
    children,
    onclick,
    variant = 'primary',
    size = 'md',
    disabled = false,
    type = 'button',
    ...rest
  } = $props();
</script>

<button
  {type}
  {onclick}
  {disabled}
  class="btn btn-{variant} btn-{size}"
  {...rest}
>
  {#if children}
    {@render children()}
  {/if}
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-family: inherit;
    font-weight: var(--font-weight-medium);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), box-shadow var(--transition-fast);
    border: 1px solid transparent;
    white-space: nowrap;
    line-height: 1;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Sizes */
  .btn-sm { padding: var(--space-1) var(--space-3); font-size: var(--font-size-xs); height: 32px; }
  .btn-md { padding: var(--space-2) var(--space-4); font-size: var(--font-size-sm); height: 40px; }
  .btn-lg { padding: var(--space-3) var(--space-6); font-size: var(--font-size-base); height: 48px; }

  /* Variants */
  .btn-primary {
    background: var(--color-primary);
    color: var(--color-text-inverse);
  }
  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }
  .btn-primary:active:not(:disabled) {
    background: var(--color-primary-active);
  }

  .btn-secondary {
    background: var(--color-surface);
    color: var(--color-text-primary);
    border-color: var(--color-border);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--color-surface-hover);
  }

  .btn-outline {
    background: transparent;
    color: var(--color-primary);
    border-color: var(--color-primary);
  }
  .btn-outline:hover:not(:disabled) {
    background: var(--color-primary-bg);
  }

  .btn-danger {
    background: var(--color-danger);
    color: var(--color-text-inverse);
  }
  .btn-danger:hover:not(:disabled) {
    background: #c92a2a;
  }

  .btn-ghost {
    background: transparent;
    color: var(--color-text-secondary);
  }
  .btn-ghost:hover:not(:disabled) {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }
</style>
