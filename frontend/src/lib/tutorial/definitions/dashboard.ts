const dashboard = [
  {
    element: '.metric-grid',
    title: 'tutorial.dashboard.step1.title',
    body: 'tutorial.dashboard.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.metric-grid .metric-card:nth-child(4)',
    title: 'tutorial.dashboard.step2.title',
    body: 'tutorial.dashboard.step2.body',
    position: 'right' as const,
  },
  {
    element: '.metric-grid .metric-card:nth-child(5)',
    title: 'tutorial.dashboard.step3.title',
    body: 'tutorial.dashboard.step3.body',
    position: 'left' as const,
  },
  {
    element: '.charts-grid',
    title: 'tutorial.dashboard.step4.title',
    body: 'tutorial.dashboard.step4.body',
    position: 'top' as const,
  },
  {
    element: '.date-presets',
    title: 'tutorial.dashboard.step5.title',
    body: 'tutorial.dashboard.step5.body',
    position: 'bottom' as const,
  },
  {
    element: '.charts-grid-half .chart-col-wide:last-child, .charts-grid-half',
    title: 'tutorial.dashboard.step6.title',
    body: 'tutorial.dashboard.step6.body',
    position: 'top' as const,
  },
  {
    element: '.table-section',
    title: 'tutorial.dashboard.step7.title',
    body: 'tutorial.dashboard.step7.body',
    position: 'top' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.dashboard.step8.title',
    body: 'tutorial.dashboard.step8.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/transactions"]',
    title: 'tutorial.dashboard.step9.title',
    body: 'tutorial.dashboard.step9.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'transactions',
  },
];

export { dashboard };
