import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, waitFor, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import * as store from './TutorialStore.svelte';
import TutorialOverlay from './TutorialOverlay.svelte';

const MISSING = [
  { element: '.does-not-exist', title: 'tutorial.strategy.step1.title', body: 'tutorial.strategy.step1.body' },
  { element: '.also-missing', title: 'tutorial.strategy.step2.title', body: 'tutorial.strategy.step2.body' },
];

describe('TutorialOverlay', () => {
  beforeEach(() => {
    setLocale('en-US');
    store.abandon();
  });

  afterEach(cleanup);

  it('shows the tutorial when the first step element is missing', async () => {
    render(TutorialOverlay, { props: { definition: MISSING, page: 'missing-page' } });

    store.start('missing-page');

    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeTruthy(), {
      timeout: 4000,
    });
    expect(document.querySelector('.driver-popover').textContent).toContain('Target allocation');
  });
});
