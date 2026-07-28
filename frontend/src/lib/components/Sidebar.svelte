<script>
  import { page } from '$app/stores';

  let { open = $bindable(false) } = $props();

  const navItems = [
    { type: 'header', label: 'Overview' },
    { href: '/', label: 'Dashboard', icon: 'chart' },
    { type: 'header', label: 'Activity' },
    { href: '/transactions', label: 'Transactions', icon: 'list' },
    { href: '/transfers/new', label: 'Transfer', icon: 'transfer' },
    { href: '/income', label: 'Income', icon: 'income' },
    { type: 'header', label: 'Investments' },
    { href: '/portfolio-assets', label: 'Portfolio Assets', icon: 'portfolio' },
    { href: '/dividends', label: 'Dividends', icon: 'dividend' },
    { href: '/performance', label: 'Performance', icon: 'performance' },
    { type: 'header', label: 'Analysis' },
    { href: '/cash-flow', label: 'Cash Flow', icon: 'cashflow' },
    { type: 'divider' },
    { type: 'header', label: 'Setup' },
    { href: '/entities', label: 'Entities', icon: 'building' },
    { href: '/market-assets', label: 'Market Assets', icon: 'market' },
    { href: '/currencies', label: 'Currencies', icon: 'currency' },
    { href: '/schedules', label: 'Schedules', icon: 'schedule' },
    { href: '/balance-snapshots', label: 'Balances', icon: 'wallet' },
    { href: '/fiscal-exemptions', label: 'Fiscal Exemptions', icon: 'fiscal' },
  ];

  let currentPath = $derived($page.url.pathname);
</script>

<aside class="sidebar" class:open>
  <div class="sidebar-brand">
    <span class="sidebar-logo">⟁</span>
    <span class="sidebar-title">Fin Hub</span>
  </div>

  <nav class="sidebar-nav">
    {#each navItems as item}
      {#if item.type === 'header'}
        <div class="nav-header">{item.label}</div>
      {:else if item.type === 'divider'}
        <div class="nav-divider"></div>
      {:else}
        <a
          href={item.href}
          class="nav-item"
          data-current={currentPath.startsWith(item.href) && item.href !== '/' ? '' : currentPath === item.href ? '' : undefined}
        >
        <span class="nav-icon">
          {#if item.icon === 'chart'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
          {:else if item.icon === 'income'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"></circle>
              <path d="M12 7v10M9 10l3-3 3 3M9 14l3 3 3-3"></path>
            </svg>
          {:else if item.icon === 'building'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
              <line x1="9" y1="6" x2="9" y2="6.01"></line>
              <line x1="15" y1="6" x2="15" y2="6.01"></line>
              <line x1="9" y1="10" x2="9" y2="10.01"></line>
              <line x1="15" y1="10" x2="15" y2="10.01"></line>
              <line x1="9" y1="14" x2="9" y2="14.01"></line>
              <line x1="15" y1="14" x2="15" y2="14.01"></line>
              <line x1="9" y1="18" x2="15" y2="18"></line>
            </svg>
          {:else if item.icon === 'currency'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="12" rx="7" ry="9"></ellipse>
              <line x1="8" y1="10" x2="16" y2="10"></line>
              <line x1="8" y1="14" x2="16" y2="14"></line>
            </svg>
          {:else if item.icon === 'list'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="8" y1="6" x2="21" y2="6"></line>
              <line x1="8" y1="12" x2="21" y2="12"></line>
              <line x1="8" y1="18" x2="21" y2="18"></line>
              <line x1="3" y1="6" x2="3.01" y2="6"></line>
              <line x1="3" y1="12" x2="3.01" y2="12"></line>
              <line x1="3" y1="18" x2="3.01" y2="18"></line>
            </svg>
          {:else if item.icon === 'wallet'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path>
              <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path>
              <path d="M18 12a2 2 0 0 0 0 4h4v-4Z"></path>
            </svg>
          {:else if item.icon === 'transfer'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4"></path>
            </svg>
          {:else if item.icon === 'dividend'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 18V6"></path>
            </svg>
          {:else if item.icon === 'cashflow'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
          {:else if item.icon === 'performance'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
              <polyline points="16 7 22 7 22 13"></polyline>
            </svg>
          {:else if item.icon === 'market'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
            </svg>
          {:else if item.icon === 'portfolio'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            </svg>
          {:else if item.icon === 'schedule'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
          {:else if item.icon === 'fiscal'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          {/if}
        </span>
        <span class="nav-label">{item.label}</span>
      </a>
      {/if}
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

  .nav-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.1);
    margin: var(--space-2) var(--space-3);
  }

  .nav-header {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(255, 255, 255, 0.35);
    padding: var(--space-3) var(--space-3) var(--space-1) var(--space-3);
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
