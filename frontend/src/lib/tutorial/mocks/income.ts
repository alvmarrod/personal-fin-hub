const entities = [
  { id: 1, name: 'Interactive Brokers', entity_type: 'BROKER', country: 'US' },
  { id: 2, name: 'Local Bank', entity_type: 'BANK', country: 'ES' },
  { id: 3, name: 'Acme Corp', entity_type: 'EMPLOYER', country: 'ES' },
];

const currencies = ['EUR', 'USD', 'JPY', 'GBP'];

const ym = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
const now = new Date();
const cur = ym(now);
const next = ym(new Date(now.getFullYear(), now.getMonth() + 1, 1));
const prev = (n) => ym(new Date(now.getFullYear(), now.getMonth() - n, 1));

const rateInfo = {
  base: 'EUR',
  latest_timestamp: new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString(),
  rates: { EUR: 1.0, USD: 1.0832, JPY: 163.45, GBP: 0.8422 },
};

const incomeMock = {
  '/currencies': currencies,
  '/entities': entities,
  '/analytics/cash-flow': {
    lines: [
      { period: cur, type: 'INCOME', currency: 'EUR', total_value: 4550.0, count: 2 },
      { period: cur, type: 'INCOME', currency: 'EUR', total_value: 18.42, count: 1 },
      { period: cur, type: 'INCOME', currency: 'EUR', total_value: 340.25, count: 2 },
      { period: prev(1), type: 'INCOME', currency: 'EUR', total_value: 3800.0, count: 1 },
      { period: prev(1), type: 'INCOME', currency: 'USD', total_value: 124.5, count: 1 },
      { period: prev(2), type: 'INCOME', currency: 'EUR', total_value: 3600.0, count: 1 },
      { period: prev(2), type: 'MONEY_OUT', currency: 'EUR', total_value: 2450.0, count: 1 },
    ],
    rate_info: rateInfo,
    summary: {
      total_income: 11433.17,
      total_expenses: 2450.0,
      total_net: 8983.17,
    },
  },
  '/analytics/income-by-source': {
    data: [
      { entity_id: 2, entity_name: 'Local Bank', period: cur, type: 'INCOME', income_category: 'other', total_value: 4550.0, currency: 'EUR' },
      { entity_id: 2, entity_name: 'Local Bank', period: prev(1), type: 'INCOME', income_category: 'other', total_value: 3800.0, currency: 'EUR' },
      { entity_id: 2, entity_name: 'Local Bank', period: prev(2), type: 'INCOME', income_category: 'other', total_value: 3600.0, currency: 'EUR' },
      { entity_id: 2, entity_name: 'Local Bank', period: prev(3), type: 'INCOME', income_category: 'other', total_value: 3200.0, currency: 'EUR' },
      { entity_id: 2, entity_name: 'Local Bank', period: prev(4), type: 'INCOME', income_category: 'other', total_value: 3150.0, currency: 'EUR' },
      { entity_id: 2, entity_name: 'Local Bank', period: cur, type: 'INCOME', income_category: 'interest', total_value: 18.42, currency: 'EUR' },
      { entity_id: 1, entity_name: 'Interactive Brokers', period: cur, type: 'INCOME', income_category: 'dividends', total_value: 124.5, currency: 'USD' },
      { entity_id: 1, entity_name: 'Interactive Brokers', period: prev(1), type: 'INCOME', income_category: 'dividends', total_value: 340.25, currency: 'EUR' },
      { entity_id: 1, entity_name: 'Interactive Brokers', period: prev(2), type: 'INCOME', income_category: 'dividends', total_value: 215.75, currency: 'EUR' },
      { entity_id: 1, entity_name: 'Interactive Brokers', period: prev(3), type: 'INCOME', income_category: 'dividends', total_value: 192.3, currency: 'USD' },
      { entity_id: 3, entity_name: 'Acme Corp', period: cur, type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
      { entity_id: 3, entity_name: 'Acme Corp', period: prev(1), type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
    ],
    display_currency: 'EUR',
    rate_info: rateInfo,
  },
  '/analytics/projected-income': {
    data: [
      { period: cur, entity_id: 2, entity_name: 'Local Bank', type: 'INCOME', income_category: 'other', total_value: 3800.0, currency: 'EUR' },
      { period: cur, entity_id: 1, entity_name: 'Interactive Brokers', type: 'INCOME', income_category: 'dividends', total_value: 124.5, currency: 'USD' },
      { period: cur, entity_id: 3, entity_name: 'Acme Corp', type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
      { period: next, entity_id: 2, entity_name: 'Local Bank', type: 'INCOME', income_category: 'other', total_value: 3800.0, currency: 'EUR' },
      { period: next, entity_id: 1, entity_name: 'Interactive Brokers', type: 'INCOME', income_category: 'dividends', total_value: 124.5, currency: 'USD' },
      { period: next, entity_id: 3, entity_name: 'Acme Corp', type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 2, 1)), entity_id: 2, entity_name: 'Local Bank', type: 'INCOME', income_category: 'other', total_value: 3800.0, currency: 'EUR' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 2, 1)), entity_id: 1, entity_name: 'Interactive Brokers', type: 'INCOME', income_category: 'dividends', total_value: 124.5, currency: 'USD' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 2, 1)), entity_id: 3, entity_name: 'Acme Corp', type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 3, 1)), entity_id: 2, entity_name: 'Local Bank', type: 'INCOME', income_category: 'other', total_value: 3800.0, currency: 'EUR' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 3, 1)), entity_id: 1, entity_name: 'Interactive Brokers', type: 'INCOME', income_category: 'dividends', total_value: 124.5, currency: 'USD' },
      { period: ym(new Date(now.getFullYear(), now.getMonth() + 3, 1)), entity_id: 3, entity_name: 'Acme Corp', type: 'INCOME', income_category: 'salary', total_value: 3200.0, currency: 'EUR' },
    ],
    display_currency: 'EUR',
    rate_info: rateInfo,
  },
  '/transactions': [
    {
      id: 101,
      timestamp: new Date(now.getFullYear(), now.getMonth(), 28, 8, 0, 0).toISOString(),
      type: 'INCOME',
      investment_transaction_category: null,
      income_category: 'salary',
      entity_id: 2,
      portfolio_asset_id: null,
      currency: 'EUR',
      total_value: 3800.0,
      notes: 'Monthly salary',
    },
    {
      id: 102,
      timestamp: new Date(now.getFullYear(), now.getMonth(), 15, 10, 30, 0).toISOString(),
      type: 'INCOME',
      investment_transaction_category: null,
      income_category: 'dividends',
      entity_id: 1,
      portfolio_asset_id: 1,
      currency: 'USD',
      total_value: 124.5,
      gross_amount: 146.47,
      net_amount: 124.5,
      notes: 'Quarterly dividend AAPL',
      payment_currency: 'EUR',
      fx_rate: 0.92,
    },
    {
      id: 103,
      timestamp: new Date(now.getFullYear(), now.getMonth(), 10, 14, 0, 0).toISOString(),
      type: 'INCOME',
      investment_transaction_category: null,
      income_category: 'dividends',
      entity_id: 1,
      portfolio_asset_id: 3,
      currency: 'EUR',
      total_value: 215.75,
      gross_amount: 253.82,
      net_amount: 215.75,
      notes: 'Quarterly dividend VWCE',
    },
    {
      id: 104,
      timestamp: new Date(now.getFullYear(), now.getMonth(), 5, 9, 15, 0).toISOString(),
      type: 'INCOME',
      investment_transaction_category: null,
      income_category: 'other',
      entity_id: 2,
      portfolio_asset_id: null,
      currency: 'EUR',
      total_value: 750.0,
      notes: 'Freelance project payment',
    },
    {
      id: 105,
      timestamp: new Date(now.getFullYear(), now.getMonth(), 1, 12, 0, 0).toISOString(),
      type: 'INCOME',
      investment_transaction_category: null,
      income_category: 'interest',
      entity_id: 2,
      portfolio_asset_id: null,
      currency: 'EUR',
      total_value: 18.42,
      notes: 'Savings account interest',
    },
  ],
};

export default incomeMock;
