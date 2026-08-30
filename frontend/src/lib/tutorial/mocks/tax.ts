const items2025 = [
  {
    transaction_id: 901,
    market_code: 'AAPL.US',
    ticker: 'AAPL',
    name: 'Apple',
    category: 'capital_gains',
    date: '2025-06-20',
    native_amount: 180.0,
    display_amount: 162.0,
    tax_owed: 34.02,
    source: 'computed',
    fiscal_rule: 'spain',
    currency: 'USD',
  },
  {
    transaction_id: 902,
    market_code: 'NVDA.US',
    ticker: 'NVDA',
    name: 'Nvidia',
    category: 'capital_gains',
    date: '2025-05-10',
    native_amount: 700.0,
    display_amount: 630.0,
    tax_owed: 132.3,
    source: 'computed',
    fiscal_rule: 'spain',
    currency: 'USD',
  },
  {
    transaction_id: 903,
    market_code: 'VWCE.DE',
    ticker: 'VWCE',
    name: 'Vanguard FTSE All-World',
    category: 'capital_gains',
    date: '2025-04-02',
    native_amount: 506.82,
    display_amount: 506.82,
    tax_owed: 106.43,
    source: 'computed',
    fiscal_rule: 'spain',
    currency: 'EUR',
  },
  {
    transaction_id: 904,
    market_code: null,
    ticker: null,
    name: 'Dividend withholding',
    category: 'dividends',
    date: '2025-08-01',
    native_amount: 200.0,
    display_amount: 180.0,
    tax_owed: 34.2,
    source: 'confirmed',
    fiscal_rule: 'spain',
    currency: 'USD',
  },
];

const items2024 = [
  {
    transaction_id: 801,
    market_code: 'TSLA.US',
    ticker: 'TSLA',
    name: 'Tesla',
    category: 'capital_gains',
    date: '2024-12-12',
    native_amount: -450.0,
    display_amount: -405.0,
    tax_owed: 0.0,
    source: 'computed',
    fiscal_rule: 'spain',
    currency: 'USD',
  },
  {
    transaction_id: 802,
    market_code: 'AAPL.US',
    ticker: 'AAPL',
    name: 'Apple',
    category: 'capital_gains',
    date: '2024-07-01',
    native_amount: 300.0,
    display_amount: 270.0,
    tax_owed: 51.3,
    source: 'computed',
    fiscal_rule: 'spain',
    currency: 'USD',
  },
];

const fiscal2025 = {
  fiscal_year: 2025,
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  realized_gains_taxable: 1386.82,
  dividends_taxable: 200.0,
  total_taxable: 1586.82,
  num_sells: 3,
  num_dividends: 1,
  tax_owed: {
    capital_gains: 272.75,
    dividends: 34.2,
  },
  items: items2025,
};

const fiscal2024 = {
  fiscal_year: 2024,
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  realized_gains_taxable: -150.0,
  dividends_taxable: 0.0,
  total_taxable: -150.0,
  num_sells: 2,
  num_dividends: 0,
  tax_owed: {
    capital_gains: 51.3,
  },
  items: items2024,
};

const taxData = {
  ruleset: 'spain',
  display_currency: 'EUR',
  fiscal_years: [fiscal2025, fiscal2024],
  total_taxable: 1436.82,
  total_tax_owed: 358.25,
  combined_base: 6000.0,
  rate_fallbacks: [
    {
      currency: 'USD',
      scope: 'realized_pl',
      reason: 'closest-in-time',
      requested_date: '2025-08-01',
      used_timestamp: '2025-07-31T18:00:00Z',
      count: 1,
    },
  ],
  default_ruleset: 'spain',
};

const currencies = ['EUR', 'USD', 'JPY'];

const taxMock = {
  '/analytics/taxable-pnl-extended': taxData,
  '/currencies': currencies,
};

export default taxMock;