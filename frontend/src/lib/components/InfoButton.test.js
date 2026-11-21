import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import InfoButton from './InfoButton.svelte';

const ITEMS = [
  { label: 'Core', text: 'the long-term backbone.' },
  { label: 'Reserve', text: 'cash and short-term bonds.' },
];

describe('InfoButton', () => {
  beforeEach(() => {
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('opens a modal with the explanation on click', async () => {
    render(InfoButton, {
      props: {
        title: 'Strategy layers',
        label: 'About strategy layers',
        items: ITEMS,
        note: 'Layers describe the role of a holding.',
      },
    });

    expect(screen.queryByText('Strategy layers')).toBeNull();

    await fireEvent.click(screen.getByRole('button', { name: 'About strategy layers' }));

    expect(screen.getByText('Strategy layers')).toBeTruthy();
    expect(screen.getByText('Core')).toBeTruthy();
    expect(screen.getByText(/long-term backbone/)).toBeTruthy();
    expect(screen.getByText('Reserve')).toBeTruthy();
    expect(screen.getByText(/Layers describe the role/)).toBeTruthy();
  });

  it('closes with the Accept button', async () => {
    render(InfoButton, { props: { title: 'Strategy layers', label: 'About', items: ITEMS } });

    await fireEvent.click(screen.getByRole('button', { name: 'About' }));
    await fireEvent.click(screen.getByText('Accept'));

    expect(screen.queryByText('Strategy layers')).toBeNull();
  });
});
