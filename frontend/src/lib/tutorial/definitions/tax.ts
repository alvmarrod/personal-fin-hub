const tax = [
  {
    element: '.table-wrap',
    title: 'tutorial.tax.step1.title',
    body: 'tutorial.tax.step1.body',
    position: 'top' as const,
  },
  {
    element: '.year-row:first-child',
    title: 'tutorial.tax.step2.title',
    body: 'tutorial.tax.step2.body',
    position: 'right' as const,
  },
  {
    element: '.year-row:first-child .num',
    title: 'tutorial.tax.step3.title',
    body: 'tutorial.tax.step3.body',
    position: 'right' as const,
  },
  {
    element: '.rate-warning',
    title: 'tutorial.tax.step4.title',
    body: 'tutorial.tax.step4.body',
    position: 'bottom' as const,
  },
  {
    element: '.page-actions select, .page-actions',
    title: 'tutorial.tax.step5.title',
    body: 'tutorial.tax.step5.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/cash-flow"]',
    title: 'tutorial.tax.step6.title',
    body: 'tutorial.tax.step6.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'cash-flow',
  },
];

export { tax };