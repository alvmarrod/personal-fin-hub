const currencies = [
  {
    element: '.metric-grid',
    title: 'tutorial.currencies.step1.title',
    body: 'tutorial.currencies.step1.body',
    position: 'top' as const,
  },
  {
    element: '.preset-bar',
    title: 'tutorial.currencies.step2.title',
    body: 'tutorial.currencies.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.section:first-child',
    title: 'tutorial.currencies.step3.title',
    body: 'tutorial.currencies.step3.body',
    position: 'top' as const,
  },
  {
    element: '.section:nth-child(2)',
    title: 'tutorial.currencies.step4.title',
    body: 'tutorial.currencies.step4.body',
    position: 'top' as const,
  },
  {
    element: '.page-actions select, .page-actions',
    title: 'tutorial.currencies.step5.title',
    body: 'tutorial.currencies.step5.body',
    position: 'bottom' as const,
  },
  {
    element: '.page-actions button',
    title: 'tutorial.currencies.step6.title',
    body: 'tutorial.currencies.step6.body',
    position: 'bottom' as const,
    action: 'navigate' as const,
    target_page: 'market-assets',
  },
];

export { currencies };
