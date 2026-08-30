const shownPages = $state<Set<string>>(new Set());
let active = $state(false);
let currentPage = $state('');
let currentStepIndex = $state(0);
let crossPageTarget = $state('');
let totalSteps = $state(0);
let disabled = $state(false);
let pausedMessage = $state('');

import { logger } from '$lib/logger.js';

const pageMocks: Record<string, Record<string, any>> = {};

let interceptEnabled = false;

import { enable as enableIntercept, disable as disableIntercept } from './mocks/intercept';

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

export function start(page: string, definition?: any[]) {
  logger.debug(`[tut#${(window as any).__seq + 1}->] start() page:`, page, 'mocks registered:', page in pageMocks);
  active = true;
  currentPage = page;
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = definition ? definition.length : 0;
  shownPages.add(page);
  persist();

  if (definition) {
    const lastStep = definition[definition.length - 1];
    if (lastStep?.action === 'navigate' && lastStep?.target_page) {
      crossPageTarget = lastStep.target_page;
    }
  }

  const mocks = pageMocks[page];
  if (mocks) {
    disableIntercept();
    enableIntercept(mocks);
    interceptEnabled = true;
  }
}

export function maybeStart(page: string, definition?: any[]): boolean {
  if (import.meta.env.MODE === 'test') return false;
  if (active && crossPageTarget === page) {
    resume(page, definition, pageMocks[page]);
    return true;
  }
  if (!isPageSeen(page)) {
    start(page, definition);
    return true;
  }
  return false;
}

export function next() {
  currentStepIndex++;
}

export function prev() {
  if (currentStepIndex > 0) currentStepIndex--;
}

export function skip() {
  _forceFinish();
}

export function abandon() {
  logger.debug(`[tut#${(window as any).__seq + 1}->] abandon()`, new Error().stack?.split('\n').slice(2, 4).join(' | '));
  if (interceptEnabled) {
    disableIntercept();
    interceptEnabled = false;
  }
  pausedMessage = 'tutorial.paused';
  active = false;
  currentPage = '';
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = 0;
}

export function finish() {
  if (crossPageTarget) {
    const page = currentPage;
    if (page) {
      shownPages.add(page);
      persist();
    }
    return;
  }
  _forceFinish();
}

export function resume(page: string, definition?: any[], mocks?: Record<string, any>): boolean {
  if (!crossPageTarget || crossPageTarget !== page || !active) return false;

  currentPage = page;
  currentStepIndex = 0;
  crossPageTarget = '';
  totalSteps = definition ? definition.length : 0;
  shownPages.add(page);
  persist();

  if (definition) {
    const lastStep = definition[definition.length - 1];
    if (lastStep?.action === 'navigate' && lastStep?.target_page) {
      crossPageTarget = lastStep.target_page;
    }
  }

  if (mocks) {
    disableIntercept();
    enableIntercept(mocks);
  }

  return true;
}

export function isActive() {
  return active;
}

export function isActiveFor(page: string) {
  return active && currentPage === page;
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

export function getCrossPageTarget() {
  return crossPageTarget;
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

function _forceFinish() {
  logger.debug(`[tut#${(window as any).__seq + 1}->] _forceFinish()`, new Error().stack?.split('\n').slice(2, 4).join(' | '));
  if (interceptEnabled) {
    disableIntercept();
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
