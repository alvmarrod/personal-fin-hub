const cashFlow = [
  {
    element: '.metric-grid',
    title: 'tutorial.cashFlow.step1.title',
    body: 'tutorial.cashFlow.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.preset-bar',
    title: 'tutorial.cashFlow.step2.title',
    body: 'tutorial.cashFlow.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.chart-section',
    title: 'tutorial.cashFlow.step3.title',
    body: 'tutorial.cashFlow.step3.body',
    position: 'top' as const,
  },
  {
    element: '.table-section',
    title: 'tutorial.cashFlow.step4.title',
    body: 'tutorial.cashFlow.step4.body',
    position: 'top' as const,
  },
  {
    element: 'a[href="/balance-snapshots"]',
    title: 'tutorial.cashFlow.step5.title',
    body: 'tutorial.cashFlow.step5.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'balance-snapshots',
  },
];

export { cashFlow };
