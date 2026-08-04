const entities = [
  {
    element: '.entity-table',
    title: 'tutorial.entities.step1.title',
    body: 'tutorial.entities.step1.body',
    position: 'top' as const,
  },
  {
    element: '.entity-table thead tr',
    title: 'tutorial.entities.step2.title',
    body: 'tutorial.entities.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.entity-table tbody tr:first-child',
    title: 'tutorial.entities.step3.title',
    body: 'tutorial.entities.step3.body',
    position: 'right' as const,
  },
  {
    element: '.table-section',
    title: 'tutorial.entities.step4.title',
    body: 'tutorial.entities.step4.body',
    position: 'top' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.entities.step5.title',
    body: 'tutorial.entities.step5.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/currencies"]',
    title: 'tutorial.entities.step6.title',
    body: 'tutorial.entities.step6.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'currencies',
  },
];

export { entities };
