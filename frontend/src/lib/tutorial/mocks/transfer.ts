const entities = [
  { id: 1, name: 'Interactive Brokers', entity_type: 'BROKER', country: 'US' },
  { id: 2, name: 'Local Bank', entity_type: 'BANK', country: 'ES' },
  { id: 3, name: 'N26', entity_type: 'BANK', country: 'DE' },
  { id: 4, name: 'Trade Republic', entity_type: 'BROKER', country: 'DE' },
];

const currencies = ['EUR', 'USD', 'JPY', 'GBP', 'CHF'];

const transferMock = {
  '/entities': entities,
  '/currencies': currencies,
};

export default transferMock;
