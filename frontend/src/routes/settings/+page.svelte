<script>
  import { t, locale, setLocale, localeOptions } from '$lib/i18n/index.svelte';

  let currentLocale = $derived(locale());

  function selectLocale(code) {
    setLocale(code);
  }
</script>

<div class="page-header">
  <h1 class="page-title">{t('settings.title')}</h1>
</div>

<div class="settings-section">
  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('settings.language')}</h2>
      <p>{t('settings.languageDesc')}</p>
    </div>
    <div class="setting-control">
      <div class="locale-cards">
        {#each localeOptions as opt}
          <button
            class="locale-card"
            class:active={currentLocale === opt.code}
            onclick={() => selectLocale(opt.code)}
          >
            <span class="locale-flag">{opt.code === 'en-US' ? '🇺🇸' : '🇪🇸'}</span>
            <span class="locale-label">{t(opt.code === 'en-US' ? 'settings.languageEn' : 'settings.languageEs')}</span>
            {#if currentLocale === opt.code}
              <svg class="locale-check" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            {/if}
          </button>
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .page-header {
    margin-bottom: var(--space-6);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text);
  }

  .settings-section {
    max-width: 640px;
  }

  .setting-group {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5) var(--space-6);
  }

  .setting-label {
    margin-bottom: var(--space-4);
  }

  .setting-label h2 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0 0 var(--space-1) 0;
  }

  .setting-label p {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
  }

  .locale-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
    max-width: 320px;
  }

  .locale-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    transition: border-color var(--transition-fast), background var(--transition-fast);
    position: relative;
  }

  .locale-card:hover {
    border-color: var(--color-primary);
  }

  .locale-card.active {
    border-color: var(--color-primary);
    background: var(--color-primary-light, rgba(59, 130, 246, 0.08));
  }

  .locale-flag {
    font-size: var(--font-size-lg);
    line-height: 1;
  }

  .locale-label {
    flex: 1;
    text-align: left;
  }

  .locale-check {
    color: var(--color-primary);
    flex-shrink: 0;
  }
</style>
