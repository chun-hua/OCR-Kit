import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/ocr': 'http://localhost:8765',
      '/health': 'http://localhost:8765',
    },
  },
})
