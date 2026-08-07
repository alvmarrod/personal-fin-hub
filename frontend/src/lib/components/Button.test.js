import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import Button from './Button.svelte';

afterEach(cleanup);

describe('Button', () => {
  it('renders a button element', () => {
    const { container } = render(Button);
    expect(container.querySelector('button')).toBeTruthy();
  });

  it('applies primary variant class by default', () => {
    const { container } = render(Button);
    expect(container.querySelector('.btn-primary')).toBeTruthy();
  });

  it('applies secondary variant class', () => {
    const { container } = render(Button, { props: { variant: 'secondary' } });
    expect(container.querySelector('.btn-secondary')).toBeTruthy();
  });

  it('applies sm size class', () => {
    const { container } = render(Button, { props: { size: 'sm' } });
    expect(container.querySelector('.btn-sm')).toBeTruthy();
  });

  it('sets disabled attribute', () => {
    const { container } = render(Button, { props: { disabled: true } });
    expect(container.querySelector('button').disabled).toBe(true);
  });

  it('sets type attribute', () => {
    const { container } = render(Button, { props: { type: 'submit' } });
    expect(container.querySelector('button').getAttribute('type')).toBe('submit');
  });
});
