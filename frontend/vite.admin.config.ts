import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The operator's page (D-ADMIN-005): its own pass, run after the shops' build into the same dist without emptying it, so
// that the shops' files stay byte-identical and no byte of this page reaches theirs. It writes dist/admin/ only. In
// development the shops' config (vite.config.ts) serves admin/index.html at /admin/.
export default defineConfig({
  plugins: [vue()],
  publicDir: false,
  build: { target: 'es2022', outDir: 'dist', emptyOutDir: false, assetsDir: 'admin/assets', rolldownOptions: { input: 'admin/index.html' } },
})
