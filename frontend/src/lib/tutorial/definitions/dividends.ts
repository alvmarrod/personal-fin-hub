const dividends = [
  {
    element: '.metric-grid',
    title: 'tutorial.dividends.step1.title',
    body: 'tutorial.dividends.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.charts-grid',
    title: 'tutorial.dividends.step2.title',
    body: 'tutorial.dividends.step2.body',
    position: 'top' as const,
  },
  {
    element: '.table-section',
    title: 'tutorial.dividends.step3.title',
    body: 'tutorial.dividends.step3.body',
    position: 'top' as const,
  },
  {
    element: '.table-section tbody tr:first-child td:first-child',
    title: 'tutorial.dividends.step4.title',
    body: 'tutorial.dividends.step4.body',
    position: 'right' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.dividends.step5.title',
    body: 'tutorial.dividends.step5.body',
    position: 'bottom' as const,
    action: 'navigate' as const,
    target_page: 'performance',
  },
];

export { dividends };
