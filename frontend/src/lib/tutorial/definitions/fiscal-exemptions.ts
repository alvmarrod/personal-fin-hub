const fiscalExemptions = [
  {
    element: '.data-table',
    title: 'tutorial.fiscalExemptions.step1.title',
    body: 'tutorial.fiscalExemptions.step1.body',
    position: 'top' as const,
  },
  {
    element: '.data-table tbody tr:first-child',
    title: 'tutorial.fiscalExemptions.step2.title',
    body: 'tutorial.fiscalExemptions.step2.body',
    position: 'right' as const,
  },
  {
    element: '.icon-btn-disabled',
    title: 'tutorial.fiscalExemptions.step3.title',
    body: 'tutorial.fiscalExemptions.step3.body',
    position: 'bottom' as const,
  },
  {
    element: '.page-header button',
    title: 'tutorial.fiscalExemptions.step4.title',
    body: 'tutorial.fiscalExemptions.step4.body',
    position: 'bottom' as const,
    action: 'navigate' as const,
    target_page: 'settings',
  },
];

export { fiscalExemptions };
