import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/health': 'http://localhost:8000',
      '/capabilities': 'http://localhost:8000',
      '/ingest': 'http://localhost:8000',
      '/query': 'http://localhost:8000',
      '/queries': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/models': 'http://localhost:8000',
      '/conversations': 'http://localhost:8000',
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
