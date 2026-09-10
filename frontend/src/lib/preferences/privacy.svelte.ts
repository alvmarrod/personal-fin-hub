let _hidden: boolean = $state(false);

export function privacyHidden(): boolean {
  return _hidden;
}

export function togglePrivacy(): void {
  _hidden = !_hidden;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('privacyHidden', String(_hidden));
  }
}

export function initPrivacy(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem('privacyHidden');
  if (saved === 'true') _hidden = true;
}
