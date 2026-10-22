import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Orice cerere catre /api/* este redirectionata automat catre Flask (port 5555)
      '/api': {
        target: 'http://localhost:5555',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://localhost:5555',
        changeOrigin: true,
      },
      '/callback': {
        target: 'http://localhost:5555',
        changeOrigin: true,
      }
    }
  }
})
