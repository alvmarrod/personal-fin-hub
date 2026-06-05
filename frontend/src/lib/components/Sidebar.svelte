<script>
  let { open = $bindable(false) } = $props();

  const navItems = [
    { href: '/', label: 'Dashboard', icon: 'chart' },
  ];
</script>

<aside class="sidebar" class:open>
  <div class="sidebar-brand">
    <span class="sidebar-logo">⟁</span>
    <span class="sidebar-title">Fin Hub</span>
  </div>

  <nav class="sidebar-nav">
    {#each navItems as item}
      <a href={item.href} class="nav-item" data-current={item.href === '/' ? '' : undefined}>
        <span class="nav-icon">
          {#if item.icon === 'chart'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
          {/if}
        </span>
        <span class="nav-label">{item.label}</span>
      </a>
    {/each}
  </nav>
</aside>

<style>
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: var(--sidebar-width);
    background: var(--sidebar-bg);
    color: var(--sidebar-text);
    display: flex;
    flex-direction: column;
    z-index: var(--z-sidebar);
    transition: transform var(--transition-base);
  }

  .sidebar-brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    height: var(--header-height);
  }

  .sidebar-logo {
    font-size: var(--font-size-xl);
    line-height: 1;
  }

  .sidebar-title {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--sidebar-text-active);
    white-space: nowrap;
  }

  .sidebar-nav {
    flex: 1;
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    color: var(--sidebar-text);
    text-decoration: none;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .nav-item:hover {
    background: var(--sidebar-hover-bg);
    color: var(--sidebar-text-active);
    text-decoration: none;
  }

  .nav-item[data-current] {
    background: var(--sidebar-active-bg);
    color: var(--sidebar-text-active);
  }

  .nav-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    flex-shrink: 0;
  }

  .nav-label {
    white-space: nowrap;
  }

  @media (max-width: 768px) {
    .sidebar {
      transform: translateX(-100%);
    }

    .sidebar.open {
      transform: translateX(0);
    }
  }
</style>
