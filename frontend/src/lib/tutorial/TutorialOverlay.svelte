<script>
  import { driver } from 'driver.js';
  import 'driver.js/dist/driver.css';
  import { onMount, onDestroy } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import * as store from './TutorialStore.svelte';
  import { page } from '$app/stores';

  let { definition = [] } = $props();

  let driverInstance = null;
  let lastRoute = $derived($page.url.pathname);

  function buildSteps() {
    return definition.map((step, i) => ({
      element: step.element || undefined,
      popover: {
        title: step.title ? t(step.title) : '',
        description: step.body ? t(step.body) : '',
        side: step.position || 'bottom',
        align: 'start',
        showButtons: ['close'],
        showProgress: true,
        progressText: t('pagination.showing', {
          start: i + 1,
          end: definition.length,
          total: definition.length,
        }).replace(/\d+/g, (m) => m).replace('{start}', i + 1).replace('{end}', definition.length).replace('{total}', definition.length),
        onNextClick: () => {
          const def = definition[store.getCurrentStep()];
          if (def?.action === 'navigate') {
            // Don't advance — wait for page change
            driverInstance?.drive(store.getCurrentStep());
            return;
          }
          store.next();
          driverInstance?.moveNext();
        },
        onPrevClick: () => {
          store.prev();
          driverInstance?.movePrevious();
        },
        onCloseClick: () => {
          store.skip();
          driverInstance?.destroy();
        },
      },
    }));
  }

  function startDriver() {
    const steps = buildSteps();
    if (steps.length === 0) return;

    driverInstance = driver({
      showProgress: true,
      steps,
      animate: true,
      overlayColor: 'rgba(0, 0, 0, 0.65)',
      stageRadius: 8,
    });

    driverInstance.drive(0);
  }

  function handleRouteChange() {
    if (!store.isActive()) return;
    const def = definition[store.getCurrentStep()];
    if (def?.action === 'navigate' && def.target_page === lastRoute) {
      // User navigated to the target page
      store.next();
      if (driverInstance) {
        driverInstance.destroy();
      }
      // Restart driver with the new page's definition
      startDriver();
    }
  }

  onMount(() => {
    if (store.isActive() && store.getCurrentPage() === '') {
      // New tutorial starting
      startDriver();
    }
  });

  onDestroy(() => {
    driverInstance?.destroy();
  });
</script>
