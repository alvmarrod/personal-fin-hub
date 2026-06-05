<script>
  let { title = 'No data', message = '', icon } = $props();
</script>

<div class="empty-state">
  {#if icon}
    <div class="empty-icon">{@render icon()}</div>
  {:else}
    <div class="empty-icon-default">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
        <polyline points="13 2 13 9 20 9"></polyline>
      </svg>
    </div>
  {/if}
  <h3 class="empty-title">{title}</h3>
  {#if message}
    <p class="empty-message">{message}</p>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-12) var(--space-4);
    color: var(--color-text-muted);
  }

  .empty-icon, .empty-icon-default {
    margin-bottom: var(--space-4);
    opacity: 0.5;
  }

  .empty-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    margin-bottom: var(--space-2);
  }

  .empty-message {
    font-size: var(--font-size-sm);
    text-align: center;
    max-width: 360px;
  }
</style>
