import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env from project root (one level up)
  const env = loadEnv(mode, path.resolve(process.cwd(), '..'), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8002'
  const wsUrl = backendUrl.replace(/^http/, 'ws')

  return {
    plugins: [react()],
    // Ensure frontend code can also see env vars from root
    envDir: '../',
    server: {
      host: true, // Listen on all addresses
      proxy: {
        '/assets': backendUrl,
        '/tree-assets': backendUrl,
        '/upload': backendUrl,
        '/admin': backendUrl,
        '/ws': {
          target: wsUrl,
          ws: true,
        },
      },
    },
  }
})
