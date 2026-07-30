const performance = [
  {
    element: '.metric-grid',
    title: 'tutorial.performance.step1.title',
    body: 'tutorial.performance.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.section:first-of-type',
    title: 'tutorial.performance.step2.title',
    body: 'tutorial.performance.step2.body',
    position: 'top' as const,
  },
  {
    element: '.data-table',
    title: 'tutorial.performance.step3.title',
    body: 'tutorial.performance.step3.body',
    position: 'top' as const,
  },
  {
    element: '.data-table tbody tr:first-child .positive, .data-table tbody tr:first-child .negative',
    title: 'tutorial.performance.step4.title',
    body: 'tutorial.performance.step4.body',
    position: 'right' as const,
  },
  {
    element: 'a[href="/cash-flow"]',
    title: 'tutorial.performance.step5.title',
    body: 'tutorial.performance.step5.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'cash-flow',
  },
];

export { performance };
