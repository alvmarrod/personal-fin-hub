<script>
  let {
    title,
    subtitle = null,
    align = 'center',
    tight = false,
    stacked = false,
    children,
    actions,
  } = $props();
</script>

<div class="page-header" class:stacked class:tight class:align-start={align === 'start'}>
  <div class="page-heading">
    <div class="page-title-row">
      <h1 class="page-title">{title}</h1>
      {#if children}{@render children()}{/if}
    </div>
    {#if subtitle}
      <p class="page-subtitle">{subtitle}</p>
    {/if}
  </div>
  {#if actions}
    <div class="page-actions">{@render actions()}</div>
  {/if}
</div>

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-header.align-start {
    align-items: flex-start;
  }

  .page-header.tight {
    margin-bottom: var(--space-2);
  }

  .page-header.stacked {
    display: block;
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    margin: 0;
  }

  .page-subtitle {
    margin: var(--space-1) 0 0;
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
</style>
