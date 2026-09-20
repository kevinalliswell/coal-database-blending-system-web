import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// The frontend talks to the existing Flask backend under /api and /health.
// In dev, Vite proxies those to the Flask server (default 127.0.0.1:5000).
// Set VITE_USE_MOCK=false in .env to hit the real backend instead of the mock engine.
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    {
      name: 'desktop-offline-html',
      transformIndexHtml(html) {
        if (mode !== 'desktop') return html
        // Desktop uses the existing system-font fallbacks and makes no font requests.
        return html.replace(/<link\b[^>]*href="https:\/\/fonts\.(?:googleapis|gstatic)\.com[^"]*"[^>]*>\s*/g, '')
      },
    },
  ],
  // A custom mode does not load .env.production. Desktop must always use Python.
  define: mode === 'desktop' ? { 'import.meta.env.VITE_USE_MOCK': JSON.stringify('false') } : undefined,
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
}))
