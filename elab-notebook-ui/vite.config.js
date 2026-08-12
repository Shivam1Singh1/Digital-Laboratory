import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      // Records that have no page in this app (e.g. ELab Notebook) are linked to the
      // Frappe desk. Without these the dev server answers /app/* with the SPA fallback
      // and the link silently re-renders this app instead of opening the record.
      // /assets and /files are what the desk shell itself pulls in.
      '/app': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/files': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
