import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Resolve backend target from Vercel service binding (BACKEND_URL) or default to local dev server
const backendTarget = process.env.BACKEND_URL || 'http://127.0.0.1:8000'
const wsTarget = backendTarget.replace(/^http/, 'ws')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
      '/demo_videos': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})

