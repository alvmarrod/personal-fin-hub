/**
 * Version baked in at build time from package.json (see `vite.config.js`).
 * Falls back only when the define is missing (e.g. a bare Svelte import in a test).
 */
export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.0.0';
