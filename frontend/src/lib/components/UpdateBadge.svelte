<script>
  import { t } from '$lib/i18n/index.svelte';
  import { backendUpdate, frontendUpdate, dismissUpdate } from '$lib/stores/updates.svelte';

  let _backend = $derived(backendUpdate());
  let _frontend = $derived(frontendUpdate());

  let showBackend = $derived(!!_backend?.outdated);
  let showFrontend = $derived(!!_frontend?.outdated);

  function handleDismiss() {
    dismissUpdate();
  }
</script>

{#if showBackend || showFrontend}
  <div class="update-badges">
    {#if showBackend}
      <a class="badge update-badge" href={_backend.url} target="_blank" rel="noreferrer">
        <span class="badge-dot"></span>
        <span class="badge-text">{t('updates.newVersion', { component: t('updates.backend'), version: _backend.latest })}</span>
      </a>
    {/if}
    {#if showFrontend}
      <a class="badge update-badge" href={_frontend.url} target="_blank" rel="noreferrer">
        <span class="badge-dot"></span>
        <span class="badge-text">{t('updates.newVersion', { component: t('updates.frontend'), version: _frontend.latest })}</span>
      </a>
    {/if}
    <button class="badge-dismiss" onclick={handleDismiss} title={t('health.dismiss')}>×</button>
  </div>
{/if}

<style>
  .update-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-6);
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-full);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .update-badge {
    background: var(--color-warning-light, rgba(240, 140, 0, 0.1));
    color: var(--color-warning, #856404);
    text-decoration: none;
  }

  .update-badge:hover {
    text-decoration: underline;
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--color-warning, #f08c00);
  }

  .badge-text {
    white-space: nowrap;
  }

  .badge-dismiss {
    background: none;
    border: none;
    padding: 0;
    margin-left: auto;
    font-size: var(--font-size-sm);
    line-height: 1;
    cursor: pointer;
    color: var(--color-text-secondary);
    opacity: 0.6;
    transition: opacity var(--transition-fast);
  }

  .badge-dismiss:hover {
    opacity: 1;
  }
</style>
