/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  build: { target: 'es2022', rolldownOptions: { input: { app: 'index.html', render: 'render.html' } } },
  // Tests read the stylesheets as text (the name, the mark, the contrast table); by default Vitest hands them over empty.
  test: { css: true },
})
