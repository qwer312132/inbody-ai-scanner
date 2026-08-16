import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 加上這段代理設定
    proxy: {
      '/api': {
        target: 'http://localhost:8000', // 你的 FastAPI 後端網址
        changeOrigin: true
      }
    }
  }
})
