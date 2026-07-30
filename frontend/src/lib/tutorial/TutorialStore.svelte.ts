const shownPages = $state<Set<string>>(new Set());
let active = $state(false);
let currentPage = $state('');
let currentStepIndex = $state(0);

const pageMocks: Record<string, Record<string, any>> = {};

let interceptEnabled = false;

export function registerMock(page: string, mocks: Record<string, any>) {
  pageMocks[page] = mocks;
}

export function init() {
  if (typeof localStorage === 'undefined') return;
  try {
    const saved = localStorage.getItem('tutorial_seen');
    if (saved) {
      const list = JSON.parse(saved);
      shownPages.clear();
      for (const p of list) shownPages.add(p);
    }
  } catch {
    // corrupt data, start fresh
  }
}

export async function start(page: string) {
  active = true;
  currentPage = page;
  currentStepIndex = 0;
  const mocks = pageMocks[page];
  if (mocks && !interceptEnabled) {
    const m = await import('./mocks/intercept');
    m.enable(mocks);
    interceptEnabled = true;
  }
}

export function next() {
  currentStepIndex++;
}

export function prev() {
  if (currentStepIndex > 0) currentStepIndex--;
}

export async function skip() {
  await finish();
}

export async function finish() {
  const page = currentPage;
  if (interceptEnabled) {
    const m = await import('./mocks/intercept');
    m.disable();
    interceptEnabled = false;
  }
  active = false;
  currentPage = '';
  currentStepIndex = 0;
  if (page) {
    shownPages.add(page);
    persist();
  }
}

export function resume() {
  // Called by pages that detect a cross-page tutorial continuation
  // Already in active state; just need to ensure step index is correct
}

export function isActive() {
  return active;
}

export function isPageSeen(page: string) {
  return shownPages.has(page);
}

export function getCurrentPage() {
  return currentPage;
}

export function getCurrentStep() {
  return currentStepIndex;
}

function persist() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('tutorial_seen', JSON.stringify([...shownPages]));
  }
}
