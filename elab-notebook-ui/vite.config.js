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
      },
      // Attachments uploaded from the Result-tab editors are private, so they
      // live under /private/files. Without this the dev server answers them with
      // the SPA fallback and an embedded <img> receives HTML - which is what the
      // broken-image icon was. Frappe serves these fine to a logged-in session
      // (verified: 200 image/png with a valid token, 403 without), so the only
      // thing missing in dev was the route. In production the SPA is served by
      // Frappe itself and this proxy is not involved.
      '/private': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
