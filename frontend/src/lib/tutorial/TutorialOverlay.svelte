<script>
  import { driver } from 'driver.js';
  import 'driver.js/dist/driver.css';
  import { onMount, onDestroy } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import * as store from './TutorialStore.svelte';

  let { definition = [], page = '', onfinish = null } = $props();

  let driverInstance = null;
  let confirmSkip = $state(false);

  let isActive = $derived(store.isActive());
  let currentPage = $derived(store.getCurrentPage());

  function buildSteps() {
    return definition.map((step, i) => {
      const isNav = step.action === 'navigate';
      let buttons = [];
      if (!isNav) {
        if (i === 0) buttons = ['next', 'close'];
        else if (i === definition.length - 1) buttons = ['previous', 'close'];
        else buttons = ['previous', 'next', 'close'];
      }

      return {
        element: step.element || undefined,
        popover: {
          title: step.title ? t(step.title) : '',
          description: step.body ? t(step.body) : '',
          side: step.position || 'bottom',
          align: 'start',
          showButtons: buttons,
          showProgress: true,
          progressText: `Step ${i + 1} of ${definition.length}`,
          onNextClick: () => {
            store.next();
            driverInstance?.moveNext();
          },
          onPrevClick: () => {
            store.prev();
            driverInstance?.movePrevious();
          },
          onCloseClick: async () => {
            confirmSkip = true;
          },
        },
      };
    });
  }

  function handleConfirmSkip() {
    confirmSkip = false;
    driverInstance?.destroy();
    store.skip();
    onfinish?.();
  }

  function handleCancelSkip() {
    confirmSkip = false;
  }

  function startDriver() {
    const steps = buildSteps();
    if (steps.length === 0) return;
    driverInstance?.destroy();
    driverInstance = driver({
      showProgress: true,
      steps,
      animate: true,
      overlayColor: 'rgba(0, 0, 0, 0.65)',
      stageRadius: 8,
      onDestroyed: () => { driverInstance = null; },
    });
    driverInstance.drive(store.getCurrentStep());
  }

  let pausedToast = $state('');

  onMount(() => {
    const msg = store.popPausedMessage();
    if (msg) {
      pausedToast = msg;
      setTimeout(() => { pausedToast = ''; }, 5000);
    }
    if (isActive) startDriver();
  });

  onDestroy(() => {
    if (confirmSkip) {
      confirmSkip = false;
    }
    if (driverInstance) {
      driverInstance.destroy();
    }
    if (isActive && !store.isPageSeen(page)) {
      store.abandon();
    }
  });

  $effect(() => {
    if (isActive && !driverInstance && !confirmSkip) {
      startDriver();
    }
    if (!isActive && driverInstance) {
      driverInstance.destroy();
    }
  });
</script>

{#if pausedToast}
  <div class="tutorial-toast">{t(pausedToast)}</div>
{/if}

{#if confirmSkip}
  <div class="confirm-overlay">
    <div class="confirm-dialog">
      <p class="confirm-text">{t('tutorial.confirmSkip')}</p>
      <div class="confirm-actions">
        <button class="confirm-btn confirm-btn-cancel" onclick={handleCancelSkip}>{t('tutorial.continueTutorial')}</button>
        <button class="confirm-btn confirm-btn-skip" onclick={handleConfirmSkip}>{t('tutorial.skipTutorial')}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .tutorial-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--color-text-primary);
    color: var(--color-text-inverse);
    padding: var(--space-3) var(--space-5);
    border-radius: var(--radius-lg);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    z-index: 100001;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    animation: toastIn 0.3s ease;
  }

  @keyframes toastIn {
    from { opacity: 0; transform: translateX(-50%) translateY(10px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }

  .confirm-overlay {
    position: fixed;
    inset: 0;
    z-index: 100002;
    background: rgba(0, 0, 0, 0.65);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .confirm-dialog {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    max-width: 400px;
    width: 90%;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    animation: dialogIn 0.2s ease;
  }

  @keyframes dialogIn {
    from { opacity: 0; transform: scale(0.95); }
    to { opacity: 1; transform: scale(1); }
  }

  .confirm-text {
    font-size: var(--font-size-base);
    color: var(--color-text-primary);
    margin: 0 0 var(--space-5) 0;
    line-height: 1.5;
  }

  .confirm-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
  }

  .confirm-btn {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text-primary);
    transition: background var(--transition-fast);
  }

  .confirm-btn:hover {
    background: var(--color-surface-hover);
  }

  .confirm-btn-skip {
    background: var(--color-primary);
    color: var(--color-text-inverse);
    border-color: var(--color-primary);
  }

  .confirm-btn-skip:hover {
    background: var(--color-primary-hover);
  }
</style>
