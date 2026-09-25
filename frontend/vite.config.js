import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// La web compilada va dentro del paquete de Python: así en el Mac solo hace falta `uv`.
export default defineConfig({
  plugins: [svelte()],
  build: { outDir: '../fasttack/web', emptyOutDir: true, chunkSizeWarningLimit: 1200 },
  server: { proxy: { '/api': 'http://localhost:8000' } },
});
