<script>
  import { t } from '$lib/i18n/index.svelte';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';

  let { title = '', label = title, items = [], note = '' } = $props();

  let open = $state(false);
  function close() {
    open = false;
  }
</script>

<button type="button" class="info-btn" aria-label={label} onclick={() => (open = true)}>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
</button>

<Modal {open} onclose={close} {title} size="sm">
  <div class="info-body">
    {#each items as item (item.label)}
      <p><strong>{item.label}</strong> — {item.text}</p>
    {/each}
    {#if note}
      <p class="info-note">{note}</p>
    {/if}
    <div class="form-actions">
      <Button variant="primary" onclick={close}>{t('common.accept')}</Button>
    </div>
  </div>
</Modal>

<style>
  .info-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    padding: 0;
    border: none;
    background: none;
    color: var(--color-text-muted);
    cursor: help;
    border-radius: var(--radius-full);
    outline: none;
    transition: color var(--transition-fast);
  }

  .info-btn:hover,
  .info-btn:focus-visible {
    color: var(--color-primary);
  }

  .info-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .info-body p {
    margin: 0;
    font-size: var(--font-size-sm);
    line-height: 1.5;
    color: var(--color-text-primary);
  }

  .info-note {
    color: var(--color-text-muted) !important;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    padding-top: var(--space-2);
  }
</style>
