<script>
  let { label, error, required = false, children } = $props();
</script>

<div class="form-field">
  {#if label}
    <span class="form-label">
      {label}
      {#if required}
        <span class="required">*</span>
      {/if}
    </span>
  {/if}
  {#if children}
    {@render children()}
  {/if}
  {#if error}
    <p class="form-error">{error}</p>
  {/if}
</div>

<style>
  .form-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .form-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
  }

  .required {
    color: var(--color-danger);
    margin-left: var(--space-1);
  }

  .form-error {
    font-size: var(--font-size-xs);
    color: var(--color-danger);
    margin-top: var(--space-1);
  }
</style>
