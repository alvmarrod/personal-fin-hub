import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte({ compilerOptions: { runes: true } })],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.js'],
  },
  resolve: {
    alias: {
      '$lib': '/src/lib',
    },
    conditions: ['browser'],
  },
});
