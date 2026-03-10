import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Vite 7 configuration for the fupan frontend.
 *
 * In development, all /api requests are proxied to the Django dev server
 * so that CORS is not an issue locally.
 *
 * In production, Nginx handles routing: /api/ → Gunicorn, / → dist/.
 */
export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000,
    proxy: {
      // Forward every request starting with /api to the Django backend.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    // Vite 7 default: target browsers that are "Baseline Widely Available"
    // (released ≥ 2.5 years ago). Override here if you need wider support.
    target: 'baseline-widely-available',
    outDir: 'dist',
    emptyOutDir: true,
  },
});
