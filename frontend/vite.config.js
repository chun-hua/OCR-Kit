import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const apiTarget = process.env.OCR_API_TARGET || 'http://localhost:8765'
const devPort = Number(process.env.VITE_PORT || 5173)

export default defineConfig({
  plugins: [vue()],
  server: {
    port: devPort,
    proxy: {
      '/ocr': apiTarget,
      '/health': apiTarget,
    },
  },
})
