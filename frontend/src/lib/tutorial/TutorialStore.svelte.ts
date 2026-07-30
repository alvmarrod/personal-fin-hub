const shownPages = $state<Set<string>>(new Set());
let active = $state(false);
let currentPage = $state('');
let currentStepIndex = $state(0);
let crossPageTarget = $state('');
let totalSteps = $state(0);
let disabled = $state(false);
let pausedMessage = $state('');

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
  try {
    disabled = localStorage.getItem('tutorial_disabled') === '1';
  } catch {
    disabled = false;
  }
}

export async function start(page: string, definition?: any[]) {
  active = true;
  currentPage = page;
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = definition ? definition.length : 0;

  if (definition) {
    const lastStep = definition[definition.length - 1];
    if (lastStep?.action === 'navigate' && lastStep?.target_page) {
      crossPageTarget = lastStep.target_page;
    }
  }

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
  await _forceFinish();
}

export async function abandon() {
  if (interceptEnabled) {
    const m = await import('./mocks/intercept');
    m.disable();
    interceptEnabled = false;
  }
  pausedMessage = 'tutorial.paused';
  active = false;
  currentPage = '';
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = 0;
}

export async function finish() {
  if (crossPageTarget) {
    const page = currentPage;
    if (page) {
      shownPages.add(page);
      persist();
    }
    return;
  }
  await _forceFinish();
}

export async function resume(page: string, definition?: any[], mocks?: Record<string, any>): Promise<boolean> {
  if (!crossPageTarget || crossPageTarget !== page || !active) return false;

  currentPage = page;
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = definition ? definition.length : 0;

  if (definition) {
    const lastStep = definition[definition.length - 1];
    if (lastStep?.action === 'navigate' && lastStep?.target_page) {
      crossPageTarget = lastStep.target_page;
    }
  }

  if (mocks && interceptEnabled) {
    const m = await import('./mocks/intercept');
    m.disable();
    m.enable(mocks);
  }

  return true;
}

export function isActive() {
  return active;
}

export function isEnabled() {
  return !disabled;
}

export function setEnabled(val: boolean) {
  disabled = !val;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('tutorial_disabled', disabled ? '1' : '0');
  }
}

export function isPageSeen(page: string) {
  if (disabled) return true;
  return shownPages.has(page);
}

export function getCurrentPage() {
  return currentPage;
}

export function getCurrentStep() {
  return currentStepIndex;
}

export function getTotalSteps() {
  return totalSteps;
}

export function popPausedMessage(): string {
  const msg = pausedMessage;
  pausedMessage = '';
  return msg;
}

async function _forceFinish() {
  if (interceptEnabled) {
    const m = await import('./mocks/intercept');
    m.disable();
    interceptEnabled = false;
  }
  const page = currentPage;
  active = false;
  currentPage = '';
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = 0;
  if (page) {
    shownPages.add(page);
    persist();
  }
}

function persist() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('tutorial_seen', JSON.stringify([...shownPages]));
  }
}
