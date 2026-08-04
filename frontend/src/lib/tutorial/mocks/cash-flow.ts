const currencies = ['EUR', 'USD', 'JPY', 'GBP'];

const cashFlowData = {
  total_in: 28500.0,
  total_out: 21450.0,
  net: 7050.0,
  rate_info: {
    latest_timestamp: '2025-07-28T12:00:00',
    rates: { 'EUR/USD': 1.08, 'EUR/JPY': 158.5, 'EUR/GBP': 0.85 },
  },
  lines: [
    { period: '2025-01', type: 'MONEY_IN', currency: 'EUR', total_value: 3500.0, count: 2 },
    { period: '2025-01', type: 'MONEY_OUT', currency: 'EUR', total_value: 2800.0, count: 3 },
    { period: '2025-01', type: 'INVESTMENT_BUY', currency: 'EUR', total_value: 4000.0, count: 1 },
    { period: '2025-02', type: 'MONEY_IN', currency: 'EUR', total_value: 3500.0, count: 1 },
    { period: '2025-02', type: 'DIVIDEND', currency: 'USD', total_value: 124.5, count: 1 },
    { period: '2025-02', type: 'MONEY_OUT', currency: 'EUR', total_value: 3100.0, count: 3 },
    { period: '2025-02', type: 'INVESTMENT_BUY', currency: 'EUR', total_value: 3500.0, count: 1 },
    { period: '2025-03', type: 'MONEY_IN', currency: 'EUR', total_value: 4000.0, count: 2 },
    { period: '2025-03', type: 'MONEY_OUT', currency: 'EUR', total_value: 2950.0, count: 4 },
    { period: '2025-03', type: 'INVESTMENT_BUY', currency: 'USD', total_value: 2500.0, count: 2 },
    { period: '2025-04', type: 'MONEY_IN', currency: 'EUR', total_value: 3500.0, count: 1 },
    { period: '2025-04', type: 'INTEREST', currency: 'EUR', total_value: 15.5, count: 1 },
    { period: '2025-04', type: 'MONEY_OUT', currency: 'EUR', total_value: 3200.0, count: 3 },
    { period: '2025-04', type: 'INVESTMENT_SELL', currency: 'USD', total_value: 5200.0, count: 1 },
    { period: '2025-05', type: 'MONEY_IN', currency: 'EUR', total_value: 3500.0, count: 1 },
    { period: '2025-05', type: 'DIVIDEND', currency: 'EUR', total_value: 210.0, count: 2 },
    { period: '2025-05', type: 'MONEY_OUT', currency: 'EUR', total_value: 2700.0, count: 3 },
    { period: '2025-05', type: 'INVESTMENT_BUY', currency: 'EUR', total_value: 3800.0, count: 1 },
    { period: '2025-06', type: 'MONEY_IN', currency: 'EUR', total_value: 5000.0, count: 1 },
    { period: '2025-06', type: 'INVESTMENT_SELL', currency: 'EUR', total_value: 5431.82, count: 1 },
    { period: '2025-06', type: 'MONEY_OUT', currency: 'EUR', total_value: 2900.0, count: 3 },
    { period: '2025-06', type: 'INVESTMENT_BUY', currency: 'USD', total_value: 2200.0, count: 1 },
    { period: '2025-07', type: 'MONEY_IN', currency: 'EUR', total_value: 5518.18, count: 2 },
    { period: '2025-07', type: 'DIVIDEND', currency: 'USD', total_value: 128.0, count: 1 },
    { period: '2025-07', type: 'INTEREST', currency: 'EUR', total_value: 12.35, count: 1 },
    { period: '2025-07', type: 'MONEY_OUT', currency: 'EUR', total_value: 3500.0, count: 4 },
    { period: '2025-07', type: 'INVESTMENT_BUY', currency: 'EUR', total_value: 2500.0, count: 1 },
  ],
};

const cashFlowMock = {
  '/currencies': currencies,
  '/analytics/cash-flow': cashFlowData,
};

export default cashFlowMock;
