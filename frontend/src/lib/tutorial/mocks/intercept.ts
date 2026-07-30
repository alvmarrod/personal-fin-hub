import { api } from '../../api/client';

let _originals = null;

/**
 * Enable mock API responses during tutorial mode.
 * @param {Record<string, any>} mocks — keyed by API path (e.g. '/analytics/dashboard')
 */
export function enable(mocks) {
  if (_originals) return; // already enabled

  _originals = {
    get: api.get,
    post: api.post,
    put: api.put,
    del: api.del,
  };

  function resolve(path) {
    const clean = path.split('?')[0];
    const entry = mocks[clean];
    if (entry === undefined) return null;
    if (typeof entry === 'function') return entry(path);
    return entry;
  }

  api.get = function (path) {
    const mock = resolve(path);
    return mock !== null ? Promise.resolve(mock) : _originals.get(path);
  };

  api.post = function (path, data) {
    const mock = resolve(path);
    return mock !== null ? Promise.resolve(mock) : _originals.post(path, data);
  };

  api.put = function (path, data) {
    const mock = resolve(path);
    return mock !== null ? Promise.resolve(mock) : _originals.put(path, data);
  };

  api.del = function (path) {
    const mock = resolve(path);
    return mock !== null ? Promise.resolve(mock) : _originals.del(path);
  };
}

export function disable() {
  if (!_originals) return;
  api.get = _originals.get;
  api.post = _originals.post;
  api.put = _originals.put;
  api.del = _originals.del;
  _originals = null;
}
