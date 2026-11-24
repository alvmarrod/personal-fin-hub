import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import ModalForm from '$lib/components/ModalForm.svelte';
import FormActions from '$lib/components/FormActions.svelte';
import FormError from '$lib/components/FormError.svelte';

function snippet(text) {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` }));
}

describe('modal form components', () => {
  afterEach(cleanup);

  it('renders its children in the shared stack', () => {
    const { container } = render(ModalForm, { props: { children: snippet('field') } });
    expect(container.querySelector('.modal-form')).toBeTruthy();
    expect(screen.getByText('field')).toBeTruthy();
  });

  it('renders its children in the shared footer', () => {
    const { container } = render(FormActions, { props: { children: snippet('save') } });
    expect(container.querySelector('.form-actions')).toBeTruthy();
    expect(screen.getByText('save')).toBeTruthy();
  });

  it('shows a message and stays empty without one', () => {
    const { container } = render(FormError, { props: { message: 'Bad amount' } });
    expect(screen.getByText('Bad amount')).toBeTruthy();
    expect(container.querySelector('.form-error')).toBeTruthy();
    cleanup();

    const { container: empty } = render(FormError, { props: { message: '' } });
    expect(empty.querySelector('.form-error')).toBeNull();
  });
});
