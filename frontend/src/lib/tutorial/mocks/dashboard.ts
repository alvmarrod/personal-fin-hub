function generateHistorical() {
  const now = new Date();
  const data = [];
  let baseValue = 100000;
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const date = d.toISOString().split('T')[0];
    const noise = (Math.sin(i * 0.8) * 5000) + (i * 3500);
    const total = Math.round(baseValue + noise);
    const invested = Math.round(total * 0.78);
    data.push({ date, total_value: total, investment_value: invested });
  }
  return data;
}

const entityAlloc = [
  { category: 'Interactive Brokers', dimension: 'entity', value_pct: 62.5, value_abs: 95529.58 },
  { category: 'Local Bank', dimension: 'entity', value_pct: 37.5, value_abs: 57317.74 },
];

const assetClassAlloc = [
  { category: 'ETF', dimension: 'asset_class', value_pct: 52.6, value_abs: 80451.0 },
  { category: 'STOCK', dimension: 'asset_class', value_pct: 26.6, value_abs: 25375.0 },
  { category: 'CASH', dimension: 'asset_class', value_pct: 20.8, value_abs: 25497.32 },
];

function allocation(path) {
  if (path.includes('dimension=entity')) return entityAlloc;
  if (path.includes('dimension=asset_class')) return assetClassAlloc;
  return [];
}

const dashboardMock = {
  '/currencies': ['EUR', 'USD', 'JPY', 'GBP'],
  '/analytics/dashboard': {
    display_currency: 'EUR',
    total_portfolio_value: 152847.32,
    total_invested: 142550.0,
    investment_value: 127350.0,
    cash_balance: 25497.32,
    total_return: 10297.32,
    total_return_pct: 7.22,
    num_holdings: 5,
    unrealized_pl: 8450.5,
    realized_pl: 1846.82,
  },
  '/analytics/allocation': allocation,
  '/analytics/holdings-by-entity': [
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
  ],
  '/analytics/historical': generateHistorical(),
};

export default dashboardMock;
