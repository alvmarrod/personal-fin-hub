const marketAssets = [
  {
    element: '.filter-bar',
    title: 'tutorial.market-assets.step1.title',
    body: 'tutorial.market-assets.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.data-table',
    title: 'tutorial.market-assets.step2.title',
    body: 'tutorial.market-assets.step2.body',
    position: 'top' as const,
  },
  {
    element: '.data-table tbody tr:first-child',
    title: 'tutorial.market-assets.step3.title',
    body: 'tutorial.market-assets.step3.body',
    position: 'right' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.market-assets.step4.title',
    body: 'tutorial.market-assets.step4.body',
    position: 'bottom' as const,
  },
  {
    title: 'tutorial.market-assets.step5.title',
    body: 'tutorial.market-assets.step5.body',
    position: 'bottom' as const,
    action: 'navigate' as const,
    target_page: 'portfolio-assets',
  },
];

export { marketAssets };
