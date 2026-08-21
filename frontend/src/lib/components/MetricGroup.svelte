<script>
  let { label = '', tone = 'market', children } = $props();
</script>

<section class="metric-group tone-{tone}">
  {#if label}<span class="group-tab">{label}</span>{/if}
  <div class="group-body">
    {@render children()}
  </div>
</section>

<style>
  .metric-group {
    position: relative;
    border: 1px solid var(--group-line, var(--color-border));
    border-radius: var(--radius-md);
    padding: var(--space-3);
    margin-top: var(--space-2);
    background: transparent;
  }

  .group-tab {
    position: absolute;
    top: -0.75em;
    left: var(--space-3);
    padding: 0 var(--space-1);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--group-line, var(--color-text-muted));
    background: var(--color-bg);
    line-height: 1.5;
    white-space: nowrap;
  }

  .group-body {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: var(--space-2);
  }

  .tone-market {
    --group-line: var(--color-primary);
  }

  .tone-unrealized {
    --group-line: var(--color-baby-blue);
  }

  .tone-realized {
    --group-line: var(--color-success);
  }

  .tone-income {
    --group-line: #845ef7;
  }

  .tone-total {
    --group-line: var(--color-warning);
  }
</style>
