<script>
  import '../app.css';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import Header from '$lib/components/Header.svelte';
  import HealthBadges from '$lib/components/HealthBadges.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { initLocale, t } from '$lib/i18n/index.svelte';
  import { initCurrency } from '$lib/preferences/currency.svelte';
  import { initProfiles, hasActiveProfile } from '$lib/stores/profile.svelte.js';
  import { initHealthPolling } from '$lib/stores/health.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { logger } from '$lib/logger.js';

  let { children } = $props();
  let sidebarOpen = $state(false);
  let initialized = $state(false);

  let currentPath = $derived((page.url.pathname || '/').replace(/\/+$/, '') || '/');
  let isProfilesPath = $derived(currentPath === '/profiles');
  let authed = $derived(hasActiveProfile());

  initLocale();
  initCurrency();
  tutorialStore.init();

  $effect(() => {
    initProfiles().finally(() => {
      initialized = true;
    });
  });

  $effect(() => {
    if (!initialized) return;
    logger.debug(`[layout] guard path=${currentPath} authed=${authed}`);
    if (!authed && currentPath !== '/profiles') {
      goto('/profiles', { replaceState: true });
    } else if (authed && currentPath === '/profiles') {
      goto('/', { replaceState: true });
    }
  });

  $effect(() => {
    if (initialized) {
      logger.debug(`[layout] ready path=${currentPath} authed=${authed}`);
    }
  });

  $effect(() => {
    if (initialized && authed) {
      initHealthPolling();
    }
  });
</script>

{#if !initialized}
  <div class="loading-shell">
    <p>{t('common.loading')}</p>
  </div>
{:else if authed}
  <div class="app-shell">
    <Sidebar bind:open={sidebarOpen} />
    <div class="app-main">
      <Header onMenuClick={() => sidebarOpen = !sidebarOpen} />
      <HealthBadges />
      <main class="app-content">
        {#if children}
          {@render children()}
        {/if}
      </main>
    </div>
  </div>

  {#if sidebarOpen}
    <div class="sidebar-backdrop" onclick={() => sidebarOpen = false} role="presentation"></div>
  {/if}
{:else if isProfilesPath}
  {@render children()}
{:else}
  <div class="loading-shell">
    <p>{t('common.loading')}</p>
  </div>
{/if}

<style>
  .loading-shell {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg);
  }

  .loading-shell p {
    font-size: var(--font-size-lg);
    color: var(--color-text-muted);
  }

  .app-shell {
    display: flex;
    min-height: 100vh;
  }

  .app-main {
    flex: 1;
    margin-left: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    transition: margin-left var(--transition-base);
  }

  .app-content {
    flex: 1;
    padding: var(--space-6);
    max-width: 1280px;
    width: 100%;
    margin: 0 auto;
  }

  .sidebar-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: var(--z-modal-backdrop);
  }

  @media (max-width: 768px) {
    .app-main {
      margin-left: 0;
    }

    .sidebar-backdrop {
      display: block;
    }
  }
</style>
