<script>
  let { text = '', label = '' } = $props();
  const aria = label || text;
  let segments = $derived(
    text.split('`').map((part, i) => ({ part, code: i % 2 === 1 })),
  );
</script>

<span class="info-tip" tabindex="0" role="button" aria-label={aria}>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
  <span class="info-tip-popover" role="tooltip">
    {#each segments as s (s.code + s.part)}
      {#if s.code}<code class="info-tip-code">{s.part}</code>{:else}{s.part}{/if}
    {/each}
  </span>
</span>

<style>
  .info-tip {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: var(--color-text-muted);
    cursor: help;
    border-radius: var(--radius-full);
    outline: none;
    transition: color var(--transition-fast);
  }

  .info-tip:hover,
  .info-tip:focus-visible {
    color: var(--color-primary);
  }

  .info-tip-popover {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 40;
    visibility: hidden;
    opacity: 0;
    transform: translateY(-4px);
    transition: opacity var(--transition-fast), transform var(--transition-fast), visibility var(--transition-fast);
    width: max-content;
    max-width: 280px;
    padding: var(--space-2) var(--space-3);
    background: var(--color-surface);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    font-size: var(--font-size-sm);
    line-height: 1.5;
    white-space: normal;
    text-align: left;
    pointer-events: none;
  }

  .info-tip:hover .info-tip-popover,
  .info-tip:focus-visible .info-tip-popover {
    visibility: visible;
    opacity: 1;
    transform: translateY(0);
  }

  .info-tip-code {
    font-family: var(--font-mono);
    font-size: 0.8em;
    background: var(--color-surface-active);
    border: 1px solid var(--color-border-light);
    border-radius: var(--radius-sm);
    padding: 0 0.2em;
  }
</style>
