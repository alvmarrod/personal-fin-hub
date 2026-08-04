const transfer = [
  {
    element: '.form-card',
    title: 'tutorial.transfer.step1.title',
    body: 'tutorial.transfer.step1.body',
    position: 'top' as const,
  },
  {
    element: '.entity-select:first-child',
    title: 'tutorial.transfer.step2.title',
    body: 'tutorial.transfer.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.entity-select:last-child',
    title: 'tutorial.transfer.step3.title',
    body: 'tutorial.transfer.step3.body',
    position: 'bottom' as const,
  },
  {
    element: '.form-grid-three',
    title: 'tutorial.transfer.step4.title',
    body: 'tutorial.transfer.step4.body',
    position: 'top' as const,
  },
  {
    element: '.form-actions',
    title: 'tutorial.transfer.step5.title',
    body: 'tutorial.transfer.step5.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/income"]',
    title: 'tutorial.transfer.step6.title',
    body: 'tutorial.transfer.step6.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'income',
  },
];

export { transfer };
