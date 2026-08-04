const currencies = ['EUR', 'USD', 'JPY', 'GBP', 'CHF'];

const marketAssets = [
  { market_code: 'IWDA.AS', ticker: 'IWDA', asset_type: 'ETF', asset_class: 'ETF', currency_code: 'EUR', name: 'iShares Core MSCI World UCITS ETF', exchange: 'EURONEXT' },
  { market_code: 'EMIM.AS', ticker: 'EMIM', asset_type: 'ETF', asset_class: 'ETF', currency_code: 'EUR', name: 'iShares Core MSCI EM IMI UCITS ETF', exchange: 'EURONEXT' },
  { market_code: 'VWCE.DE', ticker: 'VWCE', asset_type: 'ETF', asset_class: 'ETF', currency_code: 'EUR', name: 'Vanguard FTSE All-World UCITS ETF', exchange: 'XETRA' },
  { market_code: 'AAPL.US', ticker: 'AAPL', asset_type: 'STOCK', asset_class: 'STOCK', currency_code: 'USD', name: 'Apple Inc.', exchange: 'NASDAQ' },
  { market_code: 'NVDA.US', ticker: 'NVDA', asset_type: 'STOCK', asset_class: 'STOCK', currency_code: 'USD', name: 'NVIDIA Corporation', exchange: 'NASDAQ' },
];

const portfolioAssets = [
  {
    id: 1,
    market_code: 'VWCE.DE',
    distribution_type: 'ACCUMULATING',
    layer: 'CORE',
    tactic: false,
    tracking_mode: 'AUTO',
    is_active: true,
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
    is_active: true,
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
    is_active: true,
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
    is_active: true,
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
    is_active: false,
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

const now = new Date();
function genDates(n) {
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    out.push(new Date(now.getFullYear(), now.getMonth() - i, 1).toISOString().split('T')[0]);
  }
  return out;
}

const baseValues = { 'VWCE.DE': 47376, 'AAPL.US': 9775, 'NVDA.US': 15600, 'EMIM.AS': 8040, 'AGGU.L': 792 };
const dates = genDates(12);

function pointsFor(code) {
  const base = baseValues[code] || 1000;
  return dates.map((date, i) => {
    const noise = Math.sin(i * 0.8 + code.charCodeAt(0) * 0.05) * (base * 0.06);
    const trend = i * (base * 0.01);
    return { date, value: Math.round(base + noise + trend), estimated: i > 8 };
  });
}

function valueChart() {
  const data = {};
  for (const code of Object.keys(baseValues)) {
    data[code] = pointsFor(code);
  }
  return { data };
}

function chartFor(marketCode) {
  const base = baseValues[marketCode] || 1000;
  return dates.map((date, i) => {
    const noise = Math.sin(i * 0.7 + marketCode.length * 0.1) * (base * 0.04);
    const trend = i * (base * 0.012);
    return { date, price: Math.round((base + noise + trend) * 100) / 100 };
  });
}

function priceChart(path) {
  const code = path.replace('/prices/chart/', '').split('?')[0];
  return chartFor(decodeURIComponent(code));
}

const portfolioAssetsMock = {
  '/currencies': currencies,
  '/market-assets': marketAssets,
  '/portfolio-assets': portfolioAssets,
  '/prices/value-chart': valueChart(),
  '/prices/chart/': priceChart,
};

export default portfolioAssetsMock;
