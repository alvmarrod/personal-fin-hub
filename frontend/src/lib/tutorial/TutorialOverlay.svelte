<script>
  import { driver } from 'driver.js';
  import 'driver.js/dist/driver.css';
  import { onMount, onDestroy } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import * as store from './TutorialStore.svelte';

  let { definition = [], page = '' } = $props();

  let driverInstance = null;

  let isActive = $derived(store.isActive());
  let currentStep = $derived(store.getCurrentStep());

  function buildSteps() {
    return definition.map((step, i) => {
      const isLast = i === definition.length - 1;
      const isNavigate = step.action === 'navigate';
      let buttons;

      if (isNavigate) {
        buttons = [];
      } else if (i === 0) {
        buttons = ['next', 'close'];
      } else if (isLast) {
        buttons = ['previous', 'close'];
      } else {
        buttons = ['previous', 'next', 'close'];
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
          onCloseClick: () => {
            store.finish();
            driverInstance?.destroy();
          },
        },
      };
    });
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

  onMount(() => {
    if (isActive) startDriver();
  });

  onDestroy(() => {
    driverInstance?.destroy();
  });

  $effect(() => {
    // React to store changes (e.g., start() called after mount)
    if (isActive && !driverInstance) {
      startDriver();
    }
    if (!isActive && driverInstance) {
      driverInstance.destroy();
    }
  });
</script>
