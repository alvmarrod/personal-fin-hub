import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import MetricCard from './MetricCard.svelte';

afterEach(cleanup);

describe('MetricCard', () => {
  it('renders label and value', () => {
    const { container } = render(MetricCard, { props: { label: 'Portfolio', value: 42 } });
    expect(container.querySelector('.metric-label-text').textContent).toContain('Portfolio');
    expect(container.querySelector('.metric-value').textContent).toBe('42.00');
  });

  it('shows — for null value', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: null } });
    expect(container.querySelector('.metric-value').textContent).toBe('—');
  });

  it('shows — for undefined value', () => {
    const { container } = render(MetricCard, { props: { label: 'Test' } });
    expect(container.querySelector('.metric-value').textContent).toBe('—');
  });

  it('passes pre-formatted strings through verbatim', () => {
    const { container } = render(MetricCard, { props: { label: 'Return', value: '-1.02%' } });
    expect(container.querySelector('.metric-value').textContent).toBe('-1.02%');
  });

  it('formats large numbers with k suffix', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 15847 } });
    expect(container.querySelector('.metric-value').textContent).toBe('15.8k');
  });

  it('formats very large numbers with M suffix', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 15_000_000 } });
    expect(container.querySelector('.metric-value').textContent).toBe('15.00M');
  });

  it('rounds JPY values to 0 decimals', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42.5, currencyCode: 'JPY' } });
    expect(container.querySelector('.metric-value').textContent).toBe('43');
  });

  it('shows positive change with green variant', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 100, change: 5, variant: 'positive' } });
    expect(container.querySelector('.metric-change').textContent).toContain('5%');
    expect(container.querySelector('.metric-change-positive')).toBeTruthy();
  });

  it('shows negative change with red variant', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 100, change: -3, variant: 'negative' } });
    expect(container.querySelector('.metric-change').textContent).toContain('-3%');
    expect(container.querySelector('.metric-change-negative')).toBeTruthy();
  });

  it('styles value with up arrow and green color for positive valueVariant', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42, valueVariant: 'positive' } });
    const value = container.querySelector('.metric-value');
    expect(value.querySelector('.change-arrow').textContent).toContain('▲');
    expect(value.classList.contains('metric-value-positive')).toBe(true);
  });

  it('styles value with down arrow and red color for negative valueVariant', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: -42, valueVariant: 'negative' } });
    const value = container.querySelector('.metric-value');
    expect(value.querySelector('.change-arrow').textContent).toContain('▼');
    expect(value.classList.contains('metric-value-negative')).toBe(true);
  });

  it('does not render arrow without valueVariant', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42 } });
    expect(container.querySelector('.metric-value .change-arrow')).toBeNull();
  });

  it('renders InfoTip when tooltip prop is provided', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42, tooltip: 'Help text' } });
    expect(container.querySelector('.info-tip')).toBeTruthy();
  });

  it('does not render InfoTip without tooltip prop', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42 } });
    expect(container.querySelector('.info-tip')).toBeNull();
  });

  it('applies compact class when compact prop is set', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42, compact: true } });
    expect(container.querySelector('.metric-card').classList.contains('compact')).toBe(true);
  });

  it('does not apply compact class by default', () => {
    const { container } = render(MetricCard, { props: { label: 'Test', value: 42 } });
    expect(container.querySelector('.metric-card').classList.contains('compact')).toBe(false);
  });
});
