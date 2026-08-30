import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte({ compilerOptions: { runes: true } })],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.js'],
    setupFiles: ['src/lib/tests/setup.js'],
  },
  resolve: {
    alias: {
      '$lib': '/src/lib',
      '$app/navigation': '/src/lib/tests/stubs/app-navigation.js',
    },
    conditions: ['browser'],
  },
});
