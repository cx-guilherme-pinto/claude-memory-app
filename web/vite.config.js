import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Caminhos relativos: a UI é servida pelo servidor local da app.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2020',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
