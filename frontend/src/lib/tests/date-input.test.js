import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/svelte';
import { setDateFormat } from '$lib/preferences/dateFormat.svelte';
import DateInputHarness from './DateInputHarness.svelte';

afterEach(() => {
  cleanup();
  setDateFormat('dmy');
});

function renderInput(initial = '2026-01-23') {
  const { container } = render(DateInputHarness, { props: { initial } });
  return {
    container,
    text: container.querySelector('input[type="text"]'),
    native: container.querySelector('input[type="date"]'),
    value: () => container.querySelector('[data-testid="value"]').textContent,
  };
}

describe('DateInput', () => {
  it('shows the day-first order by default', () => {
    const input = renderInput();
    expect(input.text.value).toBe('23/01/2026');
    expect(input.value()).toBe('2026-01-23');
  });

  it('shows the month-first order when selected', () => {
    setDateFormat('mdy');
    const input = renderInput();
    expect(input.text.value).toBe('01/23/2026');
  });

  it('shows ISO when selected', () => {
    setDateFormat('iso');
    const input = renderInput();
    expect(input.text.value).toBe('2026-01-23');
  });

  it('parses a typed date in the selected order', async () => {
    const input = renderInput();
    await fireEvent.input(input.text, { target: { value: '25/01/2026' } });
    expect(input.value()).toBe('2026-01-25');
    await fireEvent.blur(input.text);
    expect(input.text.value).toBe('25/01/2026');
  });

  it('parses a typed date in month-first order', async () => {
    setDateFormat('mdy');
    const input = renderInput();
    await fireEvent.input(input.text, { target: { value: '01/25/2026' } });
    expect(input.value()).toBe('2026-01-25');
  });

  it('always accepts ISO input', async () => {
    setDateFormat('mdy');
    const input = renderInput();
    await fireEvent.input(input.text, { target: { value: '2026-01-25' } });
    expect(input.value()).toBe('2026-01-25');
  });

  it('reverts invalid input on blur', async () => {
    const input = renderInput();
    await fireEvent.input(input.text, { target: { value: '31/02/2026' } });
    expect(input.value()).toBe('2026-01-23');
    await fireEvent.blur(input.text);
    expect(input.text.value).toBe('23/01/2026');
  });

  it('updates the value from the native picker', async () => {
    const input = renderInput();
    await fireEvent.change(input.native, { target: { value: '2026-02-01' } });
    expect(input.value()).toBe('2026-02-01');
    expect(input.text.value).toBe('01/02/2026');
  });
});
