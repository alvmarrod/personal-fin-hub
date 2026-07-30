const income = [
  {
    element: '.metric-grid',
    title: 'tutorial.income.step1.title',
    body: 'tutorial.income.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.preset-bar',
    title: 'tutorial.income.step2.title',
    body: 'tutorial.income.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.chart-section',
    title: 'tutorial.income.step3.title',
    body: 'tutorial.income.step3.body',
    position: 'top' as const,
  },
  {
    element: '.table-section:first-child',
    title: 'tutorial.income.step4.title',
    body: 'tutorial.income.step4.body',
    position: 'top' as const,
  },
  {
    element: '.table-section:last-child',
    title: 'tutorial.income.step5.title',
    body: 'tutorial.income.step5.body',
    position: 'top' as const,
  },
  {
    element: '.page-actions select',
    title: 'tutorial.income.step6.title',
    body: 'tutorial.income.step6.body',
    position: 'left' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.income.step7.title',
    body: 'tutorial.income.step7.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/schedules"]',
    title: 'tutorial.income.step8.title',
    body: 'tutorial.income.step8.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'schedules',
  },
];

export { income };
