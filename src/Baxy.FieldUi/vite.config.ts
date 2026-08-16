import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/model': 'http://127.0.0.1:8765',
      '/metrics': 'http://127.0.0.1:8765',
      '/settings': 'http://127.0.0.1:8765',
      '/turn': 'http://127.0.0.1:8765',
      '/events': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
})
