import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import StateDiagram from './StateDiagram.svelte';

describe('StateDiagram', () => {
  afterEach(cleanup);

  it('renders six nodes with the active one highlighted', () => {
    setLocale('en-US');
    const { container } = render(StateDiagram, { props: { currentStateId: 4, transitions: [] } });
    expect(container.querySelectorAll('.node').length).toBe(6);
    const active = container.querySelectorAll('.node.active');
    expect(active.length).toBe(1);
    expect(active[0].querySelector('.node-number').textContent.trim()).toContain('4');
  });

  it('draws muted reverse edges', () => {
    const { container } = render(StateDiagram, { props: { currentStateId: 1, transitions: [] } });
    expect(container.querySelectorAll('path[data-kind="reverse"]').length).toBe(4);
  });

  it('animates the outgoing edge for a triggered transition', () => {
    const transitions = [
      { source: 'High Real Rates', target: 'First Rate Cut', status: 'Triggered', direction: 'Forward', priority: 4 },
    ];
    const { container } = render(StateDiagram, { props: { currentStateId: 4, transitions } });
    const edge = container.querySelector('path[data-edge="4-5"]');
    expect(edge.classList.contains('edge-active')).toBe(true);
    expect(edge.classList.contains('edge-triggered')).toBe(true);
  });

  it('leaves inactive edges unanimated', () => {
    const transitions = [
      { source: 'High Real Rates', target: 'First Rate Cut', status: 'Inactive', direction: 'Forward', priority: 4 },
    ];
    const { container } = render(StateDiagram, { props: { currentStateId: 4, transitions } });
    const edge = container.querySelector('path[data-edge="4-5"]');
    expect(edge.classList.contains('edge-active')).toBe(false);
  });

  it('marks a reverse edge as emerging', () => {
    const transitions = [
      { source: 'High Real Rates', target: 'Hiking Cycle', status: 'Emerging', direction: 'Reverse', priority: 9 },
    ];
    const { container } = render(StateDiagram, { props: { currentStateId: 4, transitions } });
    const edge = container.querySelector('path[data-edge="4-3"]');
    expect(edge.classList.contains('edge-active')).toBe(true);
    expect(edge.classList.contains('edge-emerging')).toBe(true);
  });
});
