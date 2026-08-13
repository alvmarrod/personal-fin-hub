import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import InfoTip from './InfoTip.svelte';

afterEach(cleanup);

describe('InfoTip', () => {
  it('renders an SVG icon', () => {
    const { container } = render(InfoTip, { props: { text: 'Help text' } });
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('renders tooltip text in a hidden popover', () => {
    const { container } = render(InfoTip, { props: { text: 'This is help' } });
    const popover = container.querySelector('.info-tip-popover');
    expect(popover).toBeTruthy();
    expect(popover.textContent).toContain('This is help');
  });

  it('renders inline code segments between backticks', () => {
    const { container } = render(InfoTip, { props: { text: 'Use `INCOME` type' } });
    const code = container.querySelector('.info-tip-code');
    expect(code).toBeTruthy();
    expect(code.textContent).toBe('INCOME');
  });

  it('renders plain text without backticks', () => {
    const { container } = render(InfoTip, { props: { text: 'Plain text' } });
    expect(container.querySelector('.info-tip-code')).toBeNull();
  });

  it('sets aria-label from label prop', () => {
    const { container } = render(InfoTip, { props: { text: 'Help', label: 'Portfolio' } });
    const btn = container.querySelector('[role="button"]');
    expect(btn.getAttribute('aria-label')).toBe('Portfolio');
  });

  it('falls back aria-label to text when no label', () => {
    const { container } = render(InfoTip, { props: { text: 'Fallback label' } });
    const btn = container.querySelector('[role="button"]');
    expect(btn.getAttribute('aria-label')).toBe('Fallback label');
  });
});
