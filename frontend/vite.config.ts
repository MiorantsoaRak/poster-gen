/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// The two ports come from the environment when it names them (SMOKE_WEB_PORT, SMOKE_API_PORT), so that two checkouts
// can run their browser smokes at the same time; frontend/tests/browser_smoke.py reads the same two names. loadEnv,
// because the project has no Node types: it returns the process's variables of that prefix.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'SMOKE_')
  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1', port: Number(env.SMOKE_WEB_PORT ?? 5173), strictPort: true,
      proxy: { '/api': { target: `http://127.0.0.1:${env.SMOKE_API_PORT ?? 8000}`, changeOrigin: false } },
    },
    // facebook.html: the return address of Facebook's dialog (D-FB-PUBLISH-002), served at /facebook.html.
    build: { target: 'es2022', rolldownOptions: { input: { app: 'index.html', render: 'render.html', facebook: 'facebook.html' } } },
    // Tests read the stylesheets as text (the name, the mark, the contrast table); by default Vitest hands them over empty.
    test: { css: true },
  }
})
