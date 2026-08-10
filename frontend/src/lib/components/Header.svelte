<script>
  import { t } from '$lib/i18n/index.svelte';
  import { activeProfileName, logout } from '$lib/stores/profile.svelte.js';

  let { onMenuClick } = $props();

  let menuOpen = $state(false);
  let profileName = $derived(activeProfileName());

  function handleLogout() {
    menuOpen = false;
    logout();
  }

  function handleSwitch() {
    menuOpen = false;
    logout();
  }
</script>

<header class="header">
  <div class="header-left">
    <button class="menu-btn" onclick={onMenuClick} aria-label={t('header.toggleMenu')}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6"></line>
        <line x1="3" y1="12" x2="21" y2="12"></line>
        <line x1="3" y1="18" x2="21" y2="18"></line>
      </svg>
    </button>
    <span class="header-title">{t('header.title')}</span>
  </div>
  <div class="header-right">
    <div class="profile-menu">
      <button class="profile-btn" onclick={() => menuOpen = !menuOpen} aria-haspopup="true" aria-expanded={menuOpen}>
        <span class="profile-avatar">{profileName ? profileName.charAt(0).toUpperCase() : ''}</span>
        <span class="profile-name">{profileName}</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      {#if menuOpen}
        <div class="profile-dropdown" role="menu">
          <button class="dropdown-item" role="menuitem" onclick={handleSwitch}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3"></path>
              <path d="M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3"></path>
              <line x1="8" y1="12" x2="16" y2="12"></line>
            </svg>
            {t('profiles.switchProfile')}
          </button>
          <button class="dropdown-item dropdown-item-danger" role="menuitem" onclick={handleLogout}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            {t('profiles.logout')}
          </button>
        </div>
      {/if}
    </div>
  </div>
</header>

{#if menuOpen}
  <div class="menu-backdrop" onclick={() => menuOpen = false} role="presentation"></div>
{/if}

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

  .header-right {
    display: flex;
    align-items: center;
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

  .profile-menu {
    position: relative;
  }

  .profile-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    background: none;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .profile-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .profile-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--color-primary);
    color: var(--color-text-inverse);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    flex-shrink: 0;
  }

  .profile-name {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .profile-dropdown {
    position: absolute;
    top: calc(100% + var(--space-2));
    right: 0;
    min-width: 200px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-xl);
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
    z-index: var(--z-modal);
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    text-align: left;
    transition: background var(--transition-fast);
  }

  .dropdown-item:hover {
    background: var(--color-surface-hover);
  }

  .dropdown-item-danger {
    color: var(--color-danger);
  }

  .menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: calc(var(--z-header) - 1);
  }

  @media (max-width: 768px) {
    .menu-btn {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
</style>
