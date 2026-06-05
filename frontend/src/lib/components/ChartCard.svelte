<script>
  let { title, children, action = null } = $props();
</script>

<div class="chart-card">
  <div class="chart-card-header">
    <h3 class="chart-card-title">{title}</h3>
    {#if action}
      <div class="chart-card-action">{@render action()}</div>
    {/if}
  </div>
  <div class="chart-card-body">
    {#if children}
      {@render children()}
    {/if}
  </div>
</div>

<style>
  .chart-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .chart-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--color-border);
  }

  .chart-card-title {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    margin: 0;
  }

  .chart-card-body {
    padding: var(--space-5);
  }
</style>
