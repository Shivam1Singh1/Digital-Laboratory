import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'


export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/assets/elab_notebook/elab/' : '/',
  build: {
    outDir: '../elab_notebook/public/elab',
    emptyOutDir: true
  },
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },


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


      '/private': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
}))
