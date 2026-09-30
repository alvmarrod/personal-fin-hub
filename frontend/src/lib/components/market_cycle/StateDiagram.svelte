<script>
  import { t } from '$lib/i18n/index.svelte';
  import { STATES, STATE_NAMES } from '$lib/marketCycle/states.js';

  let { currentStateId = null, transitions = [] } = $props();

  const NAME = STATE_NAMES;
  const FORWARD = [
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 1],
  ];
  const REVERSE = [
    [6, 2],
    [5, 4],
    [4, 3],
    [3, 2],
  ];

  const R = 42;
  const Y = 120;
  const X0 = 90;
  const GAP = 150;
  const cx = (id) => X0 + (id - 1) * GAP;

  function forwardPath(a, b) {
    if (b === a + 1) return `M ${cx(a) + R} ${Y} L ${cx(b) - R} ${Y}`;
    // 6 -> 1 wraps beneath the row.
    return `M ${cx(a)} ${Y + R + 2} C ${cx(a)} ${Y + R + 74} ${cx(b)} ${Y + R + 74} ${cx(b)} ${Y + R + 2}`;
  }

  function reversePath(a, b) {
    const dist = a - b;
    const cy = Y - R - (34 + dist * 14);
    return `M ${cx(a)} ${Y - R - 2} C ${cx(a)} ${cy} ${cx(b)} ${cy} ${cx(b)} ${Y - R - 2}`;
  }

  const statusByEdge = $derived(
    Object.fromEntries(transitions.map((tr) => [`${tr.source}|${tr.target}`, tr.status])),
  );

  function edgeClass(a, b, kind) {
    const status = statusByEdge[`${NAME[a]}|${NAME[b]}`];
    const classes = ['edge', `edge-${kind}`];
    if (status && ['Emerging', 'Near', 'Triggered'].includes(status)) {
      classes.push('edge-active', `edge-${status.toLowerCase()}`);
    }
    return classes.join(' ');
  }
</script>

<svg
  class="state-diagram"
  viewBox="0 0 960 300"
  role="img"
  aria-label={t('marketCycle.diagramLabel')}
>
  <defs>
    <marker id="mc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
    </marker>
  </defs>

  {#each REVERSE as [a, b] (['r', a, b].join('-'))}
    <path
      class={edgeClass(a, b, 'reverse')}
      d={reversePath(a, b)}
      data-edge={`${a}-${b}`}
      data-kind="reverse"
      marker-end="url(#mc-arrow)"
    />
  {/each}

  {#each FORWARD as [a, b] (['f', a, b].join('-'))}
    <path
      class={edgeClass(a, b, 'forward')}
      d={forwardPath(a, b)}
      data-edge={`${a}-${b}`}
      data-kind="forward"
      marker-end="url(#mc-arrow)"
    />
  {/each}

  {#each STATES as state (state.id)}
    <g class="node tone-{state.tone}" class:active={state.id === currentStateId}>
      <title>{t(`marketCycle.state.${state.id}`)}</title>
      <circle cx={cx(state.id)} cy={Y} r={R}></circle>
      <text class="node-number" x={cx(state.id)} y={Y + 2} text-anchor="middle" dominant-baseline="middle">
        {state.id}{state.star ? ' ★' : ''}
      </text>
      <text class="node-name" x={cx(state.id)} y={Y + R + 22} text-anchor="middle">
        {t(`marketCycle.state.${state.id}`)}
      </text>
    </g>
  {/each}
</svg>

<style>
  .state-diagram {
    width: 100%;
    height: auto;
    display: block;
  }

  .edge {
    fill: none;
    stroke-linecap: round;
  }

  .edge-forward {
    stroke: var(--color-text-muted);
    stroke-width: 2.5;
  }

  .edge-reverse {
    stroke: var(--color-border-light);
    stroke-width: 1.5;
  }

  .edge-near {
    stroke-width: 3;
  }

  .edge-triggered {
    stroke-width: 3.5;
  }

  .edge-active {
    stroke: var(--color-warning);
    animation: mc-pulse 1.4s ease-in-out infinite;
  }

  @keyframes mc-pulse {
    0%,
    100% {
      opacity: 0.35;
    }
    50% {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .edge-active {
      animation: none;
      opacity: 0.85;
    }
  }

  .node circle {
    fill: var(--color-surface);
    stroke: var(--color-border);
    stroke-width: 2;
  }

  .node-number {
    font-size: 20px;
    font-weight: var(--font-weight-bold);
    fill: var(--color-text-secondary);
  }

  .node-name {
    font-size: 12px;
    fill: var(--color-text-muted);
  }

  .node.active .node-name {
    fill: var(--color-text-primary);
    font-weight: var(--font-weight-semibold);
  }

  .node.active.tone-red circle {
    fill: var(--color-danger);
    stroke: var(--color-danger);
  }
  .node.active.tone-amber circle {
    fill: var(--color-warning);
    stroke: var(--color-warning);
  }
  .node.active.tone-blue circle {
    fill: var(--color-primary);
    stroke: var(--color-primary);
  }
  .node.active.tone-green circle {
    fill: var(--color-success);
    stroke: var(--color-success);
  }

  .node.active .node-number {
    fill: var(--color-text-inverse);
  }
</style>
