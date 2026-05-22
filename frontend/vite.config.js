import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/dist/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/static/outputs': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
    },
  },
})
