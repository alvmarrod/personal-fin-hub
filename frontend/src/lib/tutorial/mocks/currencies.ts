const currencies = ['EUR', 'USD', 'JPY', 'GBP', 'CHF'];

const holdings = [
  {
    currency_code: 'EUR',
    total_holdings: 75872.32,
    percentage: 49.6,
    latest_raw: { EUR: 1.0, USD: 1.085, JPY: 162.5, GBP: 0.855, CHF: 0.975 },
  },
  {
    currency_code: 'USD',
    total_holdings: 43550.0,
    percentage: 28.5,
    latest_raw: { EUR: 0.92, USD: 1.0, JPY: 149.8, GBP: 0.788, CHF: 0.898 },
  },
  {
    currency_code: 'JPY',
    total_holdings: 1800000.0,
    percentage: 11.8,
    latest_raw: { EUR: 0.00615, USD: 0.00667, JPY: 1.0, GBP: 0.00526, CHF: 0.0060 },
  },
  {
    currency_code: 'GBP',
    total_holdings: 8200.0,
    percentage: 5.4,
    latest_raw: { EUR: 1.17, USD: 1.269, JPY: 190.1, GBP: 1.0, CHF: 1.14 },
  },
  {
    currency_code: 'CHF',
    total_holdings: 7200.0,
    percentage: 4.7,
    latest_raw: { EUR: 1.026, USD: 1.113, JPY: 166.8, GBP: 0.877, CHF: 1.0 },
  },
];

function generateRateChart(base) {
  const now = new Date();
  const data = [];
  const pairs = [
    { code: 'EUR', baseRate: 1.0, noiseAmp: 0.02 },
    { code: 'USD', baseRate: 1.085, noiseAmp: 0.015 },
    { code: 'JPY', baseRate: 162.5, noiseAmp: 2.0 },
    { code: 'GBP', baseRate: 0.855, noiseAmp: 0.008 },
    { code: 'CHF', baseRate: 0.975, noiseAmp: 0.012 },
  ];

  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const date = d.toISOString().split('T')[0];
    const point = { date };
    pairs.forEach(({ code, baseRate, noiseAmp }) => {
      const noise = Math.sin(i * 0.6 + (code.charCodeAt(0) * 0.1)) * noiseAmp;
      point[code] = Math.round((baseRate + noise + i * 0.002) * 10000) / 10000;
    });
    data.push(point);
  }
  return data;
}

function generateHoldingsChart() {
  const now = new Date();
  const data = [];
  const codes = ['EUR', 'USD', 'GBP'];
  const baseHoldings = { EUR: 65000, USD: 38000, GBP: 6000 };

  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const date = d.toISOString().split('T')[0];
    const point = { date };
    codes.forEach((code) => {
      point[code] = Math.round(baseHoldings[code] + Math.sin(i * 0.7) * 3000 + i * 1200);
    });
    data.push(point);
  }
  return data;
}

const currenciesMock = {
  '/currencies': currencies,
  '/currencies/holdings': holdings,
  '/currencies/rate-chart': generateRateChart('EUR'),
  '/currencies/holdings-chart': generateHoldingsChart(),
};

export default currenciesMock;
