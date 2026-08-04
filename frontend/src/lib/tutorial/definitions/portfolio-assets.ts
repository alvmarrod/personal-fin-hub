const portfolioAssets = [
  {
    element: '.page-actions select, .page-actions',
    title: 'tutorial.portfolio-assets.step1.title',
    body: 'tutorial.portfolio-assets.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.date-presets',
    title: 'tutorial.portfolio-assets.step2.title',
    body: 'tutorial.portfolio-assets.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.overview-chart',
    title: 'tutorial.portfolio-assets.step3.title',
    body: 'tutorial.portfolio-assets.step3.body',
    position: 'top' as const,
  },
  {
    element: '.filter-bar',
    title: 'tutorial.portfolio-assets.step4.title',
    body: 'tutorial.portfolio-assets.step4.body',
    position: 'bottom' as const,
  },
  {
    element: '.data-table',
    title: 'tutorial.portfolio-assets.step5.title',
    body: 'tutorial.portfolio-assets.step5.body',
    position: 'top' as const,
  },
  {
    element: '.data-table tbody tr:first-child',
    title: 'tutorial.portfolio-assets.step6.title',
    body: 'tutorial.portfolio-assets.step6.body',
    position: 'right' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.portfolio-assets.step7.title',
    body: 'tutorial.portfolio-assets.step7.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/transactions"]',
    title: 'tutorial.portfolio-assets.step8.title',
    body: 'tutorial.portfolio-assets.step8.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'transactions',
  },
];

export { portfolioAssets };
