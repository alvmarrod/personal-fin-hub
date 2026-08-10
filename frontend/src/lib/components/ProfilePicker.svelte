<script>
  import { onMount } from 'svelte';
  import Button from './Button.svelte';
  import CreateProfileModal from './modals/CreateProfileModal.svelte';
  import UnlockProfileModal from './modals/UnlockProfileModal.svelte';
  import { profiles, loadProfiles, activateProfile } from '$lib/stores/profile.svelte.js';
  import { t } from '$lib/i18n/index.svelte';

  let loading = $state(true);
  let loadError = $state('');
  let createOpen = $state(false);
  let unlockProfile = $state(null);

  let list = $derived(profiles());

  onMount(async () => {
    await refresh();
  });

  async function refresh() {
    loading = true;
    loadError = '';
    try {
      await loadProfiles();
    } catch (e) {
      loadError = e.message || t('common.errorPrefix', { resource: t('profiles.profiles') });
    } finally {
      loading = false;
    }
  }

  function select(p) {
    if (p.has_password) {
      unlockProfile = p;
    } else {
      activateProfile(p);
    }
  }
</script>

<div class="picker-shell">
  <div class="picker-card">
    <div class="picker-brand">
      <span class="picker-logo">⟁</span>
      <h1 class="picker-title">{t('profiles.pickerTitle')}</h1>
    </div>
    <p class="picker-subtitle">{t('profiles.pickerSubtitle')}</p>

    {#if loading}
      <p class="picker-hint">{t('common.loading')}</p>
    {:else if loadError}
      <p class="picker-error">{loadError}</p>
      <Button variant="outline" size="sm" onclick={refresh}>{t('common.retry')}</Button>
    {:else if list.length === 0}
      <p class="picker-hint">{t('profiles.noProfiles')}</p>
    {:else}
      <div class="profile-list">
        {#each list as p}
          <button class="profile-card" onclick={() => select(p)}>
            <div class="profile-info">
              <span class="profile-name">{p.name}</span>
              {#if p.has_password}
                <span class="profile-lock">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                  </svg>
                  {t('profiles.passwordProtected')}
                </span>
              {/if}
            </div>
            <span class="profile-action">{t('profiles.select')}</span>
          </button>
        {/each}
      </div>
    {/if}

    <div class="picker-footer">
      <Button variant="primary" onclick={() => createOpen = true}>{t('profiles.create')}</Button>
    </div>
  </div>
</div>

<CreateProfileModal open={createOpen} onclose={() => createOpen = false} />
<UnlockProfileModal open={unlockProfile !== null} onclose={() => unlockProfile = null} profile={unlockProfile} />

<style>
  .picker-shell {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-6);
    background: var(--color-bg);
  }

  .picker-card {
    width: 100%;
    max-width: 420px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    box-shadow: var(--shadow-xl);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .picker-brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .picker-logo {
    font-size: var(--font-size-2xl);
    line-height: 1;
  }

  .picker-title {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    margin: 0;
  }

  .picker-subtitle {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
    line-height: 1.5;
  }

  .profile-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .profile-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    cursor: pointer;
    text-align: left;
    transition: border-color var(--transition-fast), background var(--transition-fast);
  }

  .profile-card:hover {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }

  .profile-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .profile-name {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  .profile-lock {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .profile-action {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-primary);
  }

  .picker-footer {
    display: flex;
    justify-content: flex-end;
    padding-top: var(--space-2);
  }

  .picker-hint {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
  }

  .picker-error {
    font-size: var(--font-size-sm);
    color: var(--color-danger);
    margin: 0;
  }
</style>
