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

const balanceSnapshotsMock = {
  '/balance-snapshots': snapshots,
  '/entities': entities,
};

export default balanceSnapshotsMock;
