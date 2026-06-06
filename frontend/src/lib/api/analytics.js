import { api } from './client';
import { createCrud } from './crud';

export const analytics = {
  dashboard: () => api.get('/analytics/dashboard'),
  holdings: () => api.get('/analytics/holdings'),
  allocation: (dimension = 'layer') => api.get(`/analytics/allocation?dimension=${dimension}`),
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
  historical: (startDate, endDate, interval = 'month', entityId = null) =>
    api.get(`/analytics/historical?start_date=${startDate}&end_date=${endDate}&interval=${interval}${entityId ? `&entity_id=${entityId}` : ''}`),
  holdingsByEntity: () => api.get('/analytics/holdings-by-entity'),
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
