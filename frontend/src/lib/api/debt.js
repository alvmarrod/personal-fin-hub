import { api } from './client.js';

export const debtApi = {
  list: (params = {}) => {
    const query = new URLSearchParams();
    if (params.direction) query.set('direction', params.direction);
    if (params.status) query.set('status', params.status);
    const suffix = query.toString();
    return api.get(`/debt${suffix ? `?${suffix}` : ''}`);
  },
  get: (id) => api.get(`/debt/${id}`),
  create: (body) => api.post('/debt', body),
  update: (id, body) => api.put(`/debt/${id}`, body),
  remove: (id) => api.del(`/debt/${id}`),
  pay: (id, body) => api.post(`/debt/${id}/payments`, body),
  removePayment: (id, paymentId) => api.del(`/debt/${id}/payments/${paymentId}`),
  addRate: (id, body) => api.post(`/debt/${id}/rates`, body),
  settle: (id, body) => api.post(`/debt/${id}/settle`, body),
  cancel: (id, body) => api.post(`/debt/${id}/cancel`, body),
  plan: (id) => api.get(`/debt/${id}/plan`),
  importPlan: (id, body) => api.put(`/debt/${id}/plan`, body),
  summary: (currency) => api.get(`/debt/summary?display_currency=${encodeURIComponent(currency)}`),
  counterparties: () => api.get('/debt/counterparties'),
};
