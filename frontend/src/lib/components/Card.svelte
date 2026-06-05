<script>
  let { children, variant = 'default', padding = 'md', class: className = '' } = $props();
</script>

<div class="card card-{variant} card-pad-{padding} {className}">
  {#if children}
    {@render children()}
  {/if}
</div>

<style>
  .card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .card-default {}

  .card-highlight {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 1px var(--color-primary);
  }

  .card-metric {
    border-left: 4px solid var(--color-primary);
  }

  .card-pad-sm { padding: var(--space-3); }
  .card-pad-md { padding: var(--space-5); }
  .card-pad-lg { padding: var(--space-8); }
</style>
