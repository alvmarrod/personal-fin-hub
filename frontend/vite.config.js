import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

function startupLog() {
  return {
    name: 'startup-log',
    configureServer(server) {
      server.httpServer?.once('listening', () => {
        const address = server.httpServer.address();
        const host = address.address === '::' || address.address === '0.0.0.0' ? 'localhost' : address.address;
        const port = address.port;
        console.log(`\n  SvelteKit dev server running on http://${host}:${port}\n`);
      });
    },
  };
}

export default defineConfig({
  plugins: [sveltekit(), startupLog()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://backend:8000',
        changeOrigin: true
      }
    }
  }
});
