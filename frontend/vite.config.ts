import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const localApi = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/health': localApi,
      '/capabilities': localApi,
      '/ingest': localApi,
      '/query': localApi,
      '/queries': localApi,
      '/sessions': localApi,
      '/models': localApi,
      '/conversations': localApi,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/]react(?:-dom)?/, priority: 30 },
            { name: 'markdown', test: /node_modules[\\/](?:react-markdown|remark-|rehype-|katex)/, priority: 20 },
            { name: 'icons', test: /node_modules[\\/]lucide-react/, priority: 15 },
            { name: 'vendor', test: /node_modules/, maxSize: 250_000, priority: 10 },
          ],
        },
      },
    },
  },
});
