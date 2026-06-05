<script>
  let { size = 'md', message = 'Loading...' } = $props();
</script>

<div class="spinner-container">
  <div class="spinner spinner-{size}"></div>
  {#if message}
    <p class="spinner-message">{message}</p>
  {/if}
</div>

<style>
  .spinner-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-8);
  }

  .spinner {
    border-radius: 50%;
    border: 3px solid var(--color-border);
    border-top-color: var(--color-primary);
    animation: spin 0.7s linear infinite;
  }

  .spinner-sm { width: 20px; height: 20px; border-width: 2px; }
  .spinner-md { width: 32px; height: 32px; }
  .spinner-lg { width: 48px; height: 48px; border-width: 4px; }

  .spinner-message {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
