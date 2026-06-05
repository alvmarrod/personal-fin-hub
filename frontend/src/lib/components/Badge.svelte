<script>
  let { children, variant = 'default' } = $props();
</script>

<span class="badge badge-{variant}">
  {#if children}
    {@render children()}
  {/if}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--space-2);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    border-radius: var(--radius-full);
    white-space: nowrap;
    line-height: 1.4;
  }

  .badge-default {
    background: var(--color-surface-hover);
    color: var(--color-text-secondary);
  }

  .badge-primary {
    background: var(--color-primary-bg);
    color: var(--color-primary);
  }

  .badge-success {
    background: var(--color-success-bg);
    color: var(--color-success);
  }

  .badge-warning {
    background: var(--color-warning-bg);
    color: var(--color-warning);
  }

  .badge-danger {
    background: var(--color-danger-bg);
    color: var(--color-danger);
  }

  .badge-info {
    background: var(--color-info-bg);
    color: var(--color-info);
  }
</style>
