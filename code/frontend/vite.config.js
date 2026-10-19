import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// 用 /api 前缀代理到后端 (uvicorn 默认 8000), 同源避免 CORS。
// 后端 factory.py 仍允许 5173 直连作为兜底。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
