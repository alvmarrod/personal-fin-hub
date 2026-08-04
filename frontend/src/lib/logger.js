/**
 * Minimal leveled logger (Python-style).
 * Default level is 'info', so debug messages are suppressed.
 * Set `window.__FINHUB_LOG_LEVEL = 'debug'` to enable debug output.
 */
const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };

function currentLevel() {
  const name = typeof window !== 'undefined' ? window.__FINHUB_LOG_LEVEL : null;
  return LEVELS[name] ?? LEVELS.info;
}

function log(level, args) {
  if (LEVELS[level] < currentLevel()) return;
  const fn = console[level] ?? console.log;
  fn(...args);
}

export const logger = {
  debug: (...args) => log('debug', args),
  info: (...args) => log('info', args),
  warn: (...args) => log('warn', args),
  error: (...args) => log('error', args),
  setLevel(name) {
    if (typeof window !== 'undefined') window.__FINHUB_LOG_LEVEL = name;
  },
};
