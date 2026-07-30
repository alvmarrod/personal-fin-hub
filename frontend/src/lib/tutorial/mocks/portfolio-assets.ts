const currencies = ['EUR', 'USD', 'JPY', 'GBP', 'CHF'];

const marketAssets = [
  { market_code: 'IWDA.AS', name: 'iShares Core MSCI World UCITS ETF', currency: 'EUR', asset_class: 'ETF' },
  { market_code: 'EMIM.AS', name: 'iShares Core MSCI EM IMI UCITS ETF', currency: 'EUR', asset_class: 'ETF' },
  { market_code: 'VWCE.DE', name: 'Vanguard FTSE All-World UCITS ETF', currency: 'EUR', asset_class: 'ETF' },
  { market_code: 'AAPL.US', name: 'Apple Inc.', currency: 'USD', asset_class: 'STOCK' },
  { market_code: 'NVDA.US', name: 'NVIDIA Corporation', currency: 'USD', asset_class: 'STOCK' },
];

const portfolioAssets = [
  {
    id: 1,
    market_code: 'VWCE.DE',
    distribution_type: 'ACCUMULATING',
    layer: 'CORE',
    tactic: false,
    tracking_mode: 'AUTO',
    name: 'Vanguard FTSE All-World UCITS ETF',
    asset_class: 'ETF',
    currency_code: 'EUR',
    net_quantity: 420,
    avg_cost: 98.5,
    latest_price: 112.8,
    current_value: 47376.0,
    unrealized_pl: 6006.0,
    unrealized_pl_pct: 14.52,
    weight_pct: 31.0,
    ter_pct: 0.22,
    search_str: 'VWCE Vanguard All-World',
    status: 'active',
    country: 'IE',
  },
  {
    id: 2,
    market_code: 'AAPL.US',
    distribution_type: 'DISTRIBUTING',
    layer: 'CORE',
    tactic: false,
    tracking_mode: 'AUTO',
    name: 'Apple Inc.',
    asset_class: 'STOCK',
    currency_code: 'USD',
    net_quantity: 50,
    avg_cost: 175.2,
    latest_price: 195.5,
    current_value: 9775.0,
    unrealized_pl: 1015.0,
    unrealized_pl_pct: 11.59,
    weight_pct: 6.4,
    ter_pct: null,
    search_str: 'AAPL Apple',
    status: 'active',
    country: 'US',
  },
  {
    id: 3,
    market_code: 'NVDA.US',
    distribution_type: 'DISTRIBUTING',
    layer: 'SATELLITE',
    tactic: true,
    tracking_mode: 'AUTO',
    name: 'NVIDIA Corporation',
    asset_class: 'STOCK',
    currency_code: 'USD',
    net_quantity: 30,
    avg_cost: 450.0,
    latest_price: 520.0,
    current_value: 15600.0,
    unrealized_pl: 2100.0,
    unrealized_pl_pct: 15.56,
    weight_pct: 10.2,
    ter_pct: null,
    search_str: 'NVDA NVIDIA',
    status: 'active',
    country: 'US',
  },
  {
    id: 4,
    market_code: 'EMIM.AS',
    distribution_type: 'ACCUMULATING',
    layer: 'SATELLITE',
    tactic: false,
    tracking_mode: 'AUTO',
    name: 'iShares Core MSCI EM IMI UCITS ETF',
    asset_class: 'ETF',
    currency_code: 'EUR',
    net_quantity: 200,
    avg_cost: 35.8,
    latest_price: 40.2,
    current_value: 8040.0,
    unrealized_pl: 880.0,
    unrealized_pl_pct: 12.29,
    weight_pct: 5.3,
    ter_pct: 0.18,
    search_str: 'EMIM Emerging Markets',
    status: 'active',
    country: 'IE',
  },
  {
    id: 5,
    market_code: 'AGGU.L',
    distribution_type: 'ACCUMULATING',
    layer: 'CORE',
    tactic: false,
    tracking_mode: 'MANUAL',
    name: 'iShares Core Global Aggregate Bond UCITS ETF',
    asset_class: 'BOND',
    currency_code: 'USD',
    net_quantity: 150,
    avg_cost: 5.12,
    latest_price: 5.28,
    current_value: 792.0,
    unrealized_pl: 24.0,
    unrealized_pl_pct: 3.13,
    weight_pct: 0.5,
    ter_pct: 0.10,
    search_str: 'AGGU Global Bond Aggregate',
    status: 'paused',
    country: 'IE',
  },
];

function generateValueChart() {
  const now = new Date();
  const data = [];
  const codes = ['VWCE.DE', 'AAPL.US', 'NVDA.US', 'EMIM.AS'];
  const baseValues = { 'VWCE.DE': 47376, 'AAPL.US': 9775, 'NVDA.US': 15600, 'EMIM.AS': 8040 };

  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const date = d.toISOString().split('T')[0];
    const point = { date };
    let total = 0;
    codes.forEach((code) => {
      const noise = Math.sin(i * 0.8 + code.charCodeAt(0) * 0.05) * (baseValues[code] * 0.06);
      const trend = i * (baseValues[code] * 0.01);
      const value = Math.round(baseValues[code] + noise + trend);
      point[code] = value;
      total += value;
    });
    point['total'] = total;
    point['estimated'] = i > 8;
    data.push(point);
  }
  return data;
}

const portfolioAssetsMock = {
  '/currencies': currencies,
  '/market-assets': marketAssets,
  '/portfolio-assets': portfolioAssets,
  '/prices/value-chart': generateValueChart(),
};

export default portfolioAssetsMock;
