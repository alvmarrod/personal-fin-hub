const entities = [
  {
    id: 1,
    name: 'Interactive Brokers',
    entity_type: 'BROKER',
    country: 'US',
  },
  {
    id: 2,
    name: 'Local Bank',
    entity_type: 'BANK',
    country: 'ES',
  },
  {
    id: 3,
    name: 'ACME Corp',
    entity_type: 'EMPLOYER',
    country: 'DE',
  },
];

const holdingsByEntity = [
  {
    entity_id: 1,
    entity_name: 'Interactive Brokers',
    market_code: 'AAPL.US',
    ticker: 'AAPL',
    name: 'Apple Inc.',
    asset_type: 'STOCK',
    asset_class: 'STOCK',
    layer: 'core',
    currency: 'USD',
    net_quantity: 50,
    avg_cost: 175.2,
    total_cost: 8760,
    latest_price: 195.5,
    current_value: 9775,
    unrealized_pl: 1015,
    unrealized_pl_pct: 11.59,
    weight_pct: 6.4,
  },
  {
    entity_id: 1,
    entity_name: 'Interactive Brokers',
    market_code: 'VWCE.DE',
    ticker: 'VWCE',
    name: 'Vanguard FTSE All-World UCITS ETF',
    asset_type: 'ETF',
    asset_class: 'ETF',
    layer: 'core',
    currency: 'EUR',
    net_quantity: 420,
    avg_cost: 98.5,
    total_cost: 41370,
    latest_price: 112.8,
    current_value: 47376,
    unrealized_pl: 6006,
    unrealized_pl_pct: 14.52,
    weight_pct: 31.0,
  },
  {
    entity_id: 1,
    entity_name: 'Interactive Brokers',
    market_code: 'NVDA.US',
    ticker: 'NVDA',
    name: 'NVIDIA Corporation',
    asset_type: 'STOCK',
    asset_class: 'STOCK',
    layer: 'satellite',
    currency: 'USD',
    net_quantity: 30,
    avg_cost: 450.0,
    total_cost: 13500,
    latest_price: 520.0,
    current_value: 15600,
    unrealized_pl: 2100,
    unrealized_pl_pct: 15.56,
    weight_pct: 10.2,
  },
  {
    entity_id: 2,
    entity_name: 'Local Bank',
    market_code: 'SP500.ETF',
    ticker: 'SPY5',
    name: 'S&P 500 ETF Acc',
    asset_type: 'ETF',
    asset_class: 'ETF',
    layer: 'core',
    currency: 'EUR',
    net_quantity: 350,
    avg_cost: 80.0,
    total_cost: 28000,
    latest_price: 94.5,
    current_value: 33075,
    unrealized_pl: 5075,
    unrealized_pl_pct: 18.13,
    weight_pct: 21.6,
  },
  {
    entity_id: 2,
    entity_name: 'Local Bank',
    market_code: 'CASH',
    ticker: null,
    name: 'EUR Cash Balance',
    asset_type: 'CASH',
    asset_class: 'CASH',
    layer: 'cash',
    currency: 'EUR',
    net_quantity: null,
    avg_cost: null,
    total_cost: null,
    latest_price: null,
    current_value: 25497.32,
    unrealized_pl: null,
    unrealized_pl_pct: null,
    weight_pct: 16.7,
  },
];

function generateHistorical() {
  const now = new Date();
  const data = [];
  let baseValue = 100000;
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const date = d.toISOString().split('T')[0];
    const noise = Math.sin(i * 0.75) * 6000 + i * 3800;
    const total = Math.round(baseValue + noise);
    data.push({ date, total_value: total, investment_value: Math.round(total * 0.78) });
  }
  return data;
}

const entitiesMock = {
  '/entities': entities,
  '/currencies': ['EUR', 'USD'],
  '/analytics/holdings-by-entity': holdingsByEntity,
  '/analytics/historical': generateHistorical(),
};

export default entitiesMock;
