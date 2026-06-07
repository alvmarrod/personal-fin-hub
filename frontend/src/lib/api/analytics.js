import { api } from './client';
import { createCrud } from './crud';

export const analytics = {
  dashboard: (displayCurrency = 'USD') => api.get(`/analytics/dashboard?display_currency=${encodeURIComponent(displayCurrency)}`),
  holdings: () => api.get('/analytics/holdings'),
  allocation: (dimension = 'layer', displayCurrency = null) => {
    const params = new URLSearchParams({ dimension });
    if (displayCurrency) params.set('display_currency', displayCurrency);
    return api.get(`/analytics/allocation?${params}`);
  },
  cashFlow: (params = {}) => {
    const q = new URLSearchParams({
      group_by: params.groupBy || 'month',
      ...(params.startDate && { start_date: params.startDate }),
      ...(params.endDate && { end_date: params.endDate }),
    }).toString();
    return api.get(`/analytics/cash-flow?${q}`);
  },
  dividends: (params = {}) => {
    const q = new URLSearchParams({
      ...(params.startDate && { start_date: params.startDate }),
      ...(params.endDate && { end_date: params.endDate }),
    }).toString();
    return api.get(`/analytics/dividends?${q}`);
  },
  feesTaxes: (params = {}) => {
    const q = new URLSearchParams({
      ...(params.startDate && { start_date: params.startDate }),
      ...(params.endDate && { end_date: params.endDate }),
    }).toString();
    return api.get(`/analytics/fees-taxes?${q}`);
  },
  performance: () => api.get('/analytics/performance'),
  realizedGains: () => api.get('/analytics/realized-gains'),
  historical: (startDate, endDate, interval = 'month', entityId = null, displayCurrency = null) => {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      interval,
    });
    if (entityId) params.set('entity_id', entityId);
    if (displayCurrency) params.set('display_currency', displayCurrency);
    return api.get(`/analytics/historical?${params}`);
  },
  holdingsByEntity: (displayCurrency = null) => {
    const params = new URLSearchParams();
    if (displayCurrency) params.set('display_currency', displayCurrency);
    return api.get(`/analytics/holdings-by-entity?${params}`);
  },
  incomeBySource: (params = {}) => {
    const q = new URLSearchParams({
      group_by: params.groupBy || 'month',
      ...(params.startDate && { start_date: params.startDate }),
      ...(params.endDate && { end_date: params.endDate }),
    }).toString();
    return api.get(`/analytics/income-by-source?${q}`);
  },
};

export const currenciesApi = {
  getList: () => api.get('/currencies'),
  getLatestRate: (code, base = 'USD') =>
    api.get(`/currencies/rates/${encodeURIComponent(code)}/${encodeURIComponent(base)}`),
  getRateHistory: (code, base = 'USD') =>
    api.get(`/currencies/rates/${encodeURIComponent(code)}/${encodeURIComponent(base)}/history`),
};

export const crud = {
  entities: {
    ...createCrud('entities'),
    getDependents: (id) => api.get(`/entities/${id}/dependents`),
  },
  currencies: createCrud('currencies'),
  marketAssets: createCrud('market-assets'),
  portfolioAssets: createCrud('portfolio-assets'),
  prices: createCrud('prices'),
  transactions: createCrud('transactions'),
  transactionFees: createCrud('transaction-fees'),
  transactionTaxes: createCrud('transaction-taxes'),
  schedules: createCrud('schedules'),
  fiscalExemptions: createCrud('fiscal-exemptions'),
  balanceSnapshots: createCrud('balance-snapshots'),
};
