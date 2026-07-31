<script>
  import * as store from '../TutorialStore.svelte';
  import { t } from '$lib/i18n/index.svelte';

  let { page = '' } = $props();

  async function replay() {
    await store.start(page);
  }
</script>

<button class="replay-btn" onclick={replay} title="Replay tutorial">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
</button>

<style>
  .replay-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: none;
    border-radius: var(--radius-md);
    background: #89CFF0;
    color: #1a1a2e;
    cursor: pointer;
    transition: all var(--transition-fast);
    flex-shrink: 0;
  }

  .replay-btn:hover {
    background: #6bb5d8;
  }
</style>
