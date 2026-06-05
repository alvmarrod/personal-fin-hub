<script>
  let { onMenuClick } = $props();
</script>

<header class="header">
  <div class="header-left">
    <button class="menu-btn" onclick={onMenuClick} aria-label="Toggle menu">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6"></line>
        <line x1="3" y1="12" x2="21" y2="12"></line>
        <line x1="3" y1="18" x2="21" y2="18"></line>
      </svg>
    </button>
    <span class="header-title">Personal Fin Hub</span>
  </div>
</header>

<style>
  .header {
    position: sticky;
    top: 0;
    height: var(--header-height);
    background: var(--header-bg);
    border-bottom: 1px solid var(--header-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-6);
    z-index: var(--z-header);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .menu-btn {
    display: none;
    background: none;
    border: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-md);
  }

  .menu-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .header-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  @media (max-width: 768px) {
    .menu-btn {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
</style>
