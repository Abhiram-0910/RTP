import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy all /api/* and /token requests to the FastAPI backend.
      // This makes them same-origin from the browser's perspective,
      // completely bypassing CORS for local development.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/token': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

