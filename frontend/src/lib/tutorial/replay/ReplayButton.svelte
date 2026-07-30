<script>
  import * as store from '../TutorialStore.svelte';
  import { t } from '$lib/i18n/index.svelte';

  let { page = '' } = $props();

  function replay() {
    store.start(page);
  }
</script>

<button class="replay-btn" onclick={replay} title="Replay tutorial">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
  <span class="replay-label">{t('tutorial.replay')}</span>
</button>

<style>
  .replay-btn {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    color: var(--color-text-secondary);
    font-size: var(--font-size-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .replay-btn:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .replay-label {
    white-space: nowrap;
  }
</style>
