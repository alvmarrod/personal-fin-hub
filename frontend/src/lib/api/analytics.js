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
};

export const crud = {
  entities: createCrud('entities'),
  currencies: createCrud('currencies'),
  marketAssets: createCrud('market-assets'),
  portfolioAssets: createCrud('portfolio-assets'),
  prices: createCrud('prices'),
  transactions: createCrud('transactions'),
  transactionFees: createCrud('transaction-fees'),
  transactionTaxes: createCrud('transaction-taxes'),
  schedules: createCrud('schedules'),
  fiscalExemptions: createCrud('fiscal-exemptions'),
};
