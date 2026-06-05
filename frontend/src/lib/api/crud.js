import { api } from './client';

/**
 * Creates generic CRUD functions for a resource.
 * @param {string} resource - Plural resource name (e.g., 'entities')
 * @returns {object} { getList, getOne, create, update, remove }
 */
export function createCrud(resource) {
  return {
    getList: () => api.get(`/${resource}`),
    getOne: (id) => api.get(`/${resource}/${id}`),
    create: (data) => api.post(`/${resource}`, data),
    update: (id, data) => api.put(`/${resource}/${id}`, data),
    remove: (id) => api.del(`/${resource}/${id}`),
  };
}
