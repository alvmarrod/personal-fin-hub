const schedules = [
  {
    element: '.filter-bar',
    title: 'tutorial.schedules.step1.title',
    body: 'tutorial.schedules.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.data-table',
    title: 'tutorial.schedules.step2.title',
    body: 'tutorial.schedules.step2.body',
    position: 'top' as const,
  },
  {
    element: '.data-table tbody tr:first-child',
    title: 'tutorial.schedules.step3.title',
    body: 'tutorial.schedules.step3.body',
    position: 'right' as const,
  },
  {
    element: '.data-table thead th:nth-child(4)',
    title: 'tutorial.schedules.step4.title',
    body: 'tutorial.schedules.step4.body',
    position: 'top' as const,
  },
  {
    element: '.page-header > div:last-child button',
    title: 'tutorial.schedules.step5.title',
    body: 'tutorial.schedules.step5.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/dividends"]',
    title: 'tutorial.schedules.step6.title',
    body: 'tutorial.schedules.step6.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'dividends',
  },
];

export { schedules };
