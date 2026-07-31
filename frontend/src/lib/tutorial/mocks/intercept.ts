import { setMockStore } from '../../api/client';

let _enabled = false;

export function enable(mocks) {
  setMockStore(mocks);
  _enabled = true;
}

export function disable() {
  setMockStore(null);
  _enabled = false;
}
