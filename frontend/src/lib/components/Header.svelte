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
    <span class="header-title">Dashboard</span>
  </div>

  <div class="header-right">
    <button class="btn btn-primary btn-sm">
      + Add Asset
    </button>
    <button class="btn btn-outline btn-sm">
      + Add Income
    </button>
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

  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-family: inherit;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .btn-sm {
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-xs);
    height: 32px;
  }

  .btn-primary {
    background: var(--color-primary);
    color: var(--color-text-inverse);
  }

  .btn-primary:hover {
    background: var(--color-primary-hover);
  }

  .btn-outline {
    background: transparent;
    border-color: var(--color-border);
    color: var(--color-text-secondary);
  }

  .btn-outline:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }

  @media (max-width: 768px) {
    .menu-btn {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
</style>
