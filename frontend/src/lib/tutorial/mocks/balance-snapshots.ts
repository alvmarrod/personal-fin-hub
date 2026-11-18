const snapshots = [
  {
    id: 1,
    entity_id: 1,
    timestamp: '2025-07-28T12:00:00',
    amount: 127350.0,
    currency: 'EUR',
    notes: 'End of July portfolio valuation',
  },
  {
    id: 2,
    entity_id: 1,
    timestamp: '2025-06-30T12:00:00',
    amount: 118500.0,
    currency: 'EUR',
    notes: 'End of June portfolio valuation',
  },
  {
    id: 3,
    entity_id: 2,
    timestamp: '2025-07-28T12:00:00',
    amount: 25497.32,
    currency: 'EUR',
    notes: 'End of July savings balance',
  },
  {
    id: 4,
    entity_id: 2,
    timestamp: '2025-06-30T12:00:00',
    amount: 21450.0,
    currency: 'EUR',
    notes: 'End of June savings balance',
  },
  {
    id: 5,
    entity_id: 1,
    timestamp: '2025-05-31T12:00:00',
    amount: 112300.0,
    currency: 'EUR',
    notes: 'End of May portfolio valuation',
  },
  {
    id: 6,
    entity_id: 2,
    timestamp: '2025-05-31T12:00:00',
    amount: 19800.0,
    currency: 'EUR',
    notes: 'End of May savings balance',
  },
  {
    id: 7,
    entity_id: 1,
    timestamp: '2025-04-30T12:00:00',
    amount: 105800.0,
    currency: 'EUR',
    notes: null,
  },
];

const entities = [
  { id: 1, name: 'Interactive Brokers' },
  { id: 2, name: 'Local Bank' },
];

const balances = [
  { entity_id: 1, currency: 'EUR', balance: 127350.0 },
  { entity_id: 2, currency: 'EUR', balance: 25497.32 },
];

function cashHistory(path: string) {
  const query = new URLSearchParams(path.split('?')[1] || '');
  const entityId = Number(query.get('entity_id'));
  const currency = query.get('currency') || 'EUR';
  const pocket = balances.find((b) => b.entity_id === entityId && b.currency === currency);
  const balance = pocket?.balance ?? 0;
  return [
    { date: '2025-04', currency, balance: balance * 0.85 },
    { date: '2025-05', currency, balance: balance * 0.9 },
    { date: '2025-06', currency, balance: balance * 0.95 },
    { date: '2025-07', currency, balance },
  ];
}

const balanceSnapshotsMock = {
  '/balance-snapshots': snapshots,
  '/entities': entities,
  '/analytics/cash-balances': balances,
  '/analytics/cash-by-currency-history': cashHistory,
};

export default balanceSnapshotsMock;
