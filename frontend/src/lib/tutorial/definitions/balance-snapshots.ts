const balanceSnapshots = [
  {
    element: '.filter-bar select',
    title: 'tutorial.balanceSnapshots.step1.title',
    body: 'tutorial.balanceSnapshots.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.snapshot-table',
    title: 'tutorial.balanceSnapshots.step2.title',
    body: 'tutorial.balanceSnapshots.step2.body',
    position: 'top' as const,
  },
  {
    element: '.snapshot-table tbody tr:first-child',
    title: 'tutorial.balanceSnapshots.step3.title',
    body: 'tutorial.balanceSnapshots.step3.body',
    position: 'right' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.balanceSnapshots.step4.title',
    body: 'tutorial.balanceSnapshots.step4.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/fiscal-exemptions"]',
    title: 'tutorial.balanceSnapshots.step5.title',
    body: 'tutorial.balanceSnapshots.step5.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'fiscal-exemptions',
  },
];

export { balanceSnapshots };
