const transactions = [
  {
    element: '.filter-bar',
    title: 'tutorial.transactions.step1.title',
    body: 'tutorial.transactions.step1.body',
    position: 'bottom' as const,
  },
  {
    element: '.filter-btn:first-child',
    title: 'tutorial.transactions.step2.title',
    body: 'tutorial.transactions.step2.body',
    position: 'bottom' as const,
  },
  {
    element: '.transactions-table',
    title: 'tutorial.transactions.step3.title',
    body: 'tutorial.transactions.step3.body',
    position: 'top' as const,
  },
  {
    element: '.transactions-table tbody tr:first-child',
    title: 'tutorial.transactions.step4.title',
    body: 'tutorial.transactions.step4.body',
    position: 'right' as const,
  },
  {
    element: '.page-actions',
    title: 'tutorial.transactions.step5.title',
    body: 'tutorial.transactions.step5.body',
    position: 'bottom' as const,
  },
  {
    element: 'a[href="/transfer"]',
    title: 'tutorial.transactions.step6.title',
    body: 'tutorial.transactions.step6.body',
    position: 'right' as const,
    action: 'navigate' as const,
    target_page: 'transfer',
  },
];

export { transactions };
