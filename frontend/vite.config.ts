import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// One version for the whole project, written in ../VERSION.
const appVersion = readFileSync(new URL('../VERSION', import.meta.url), 'utf8').trim();

const localApi = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), {
    // The page names the version it was built from, in dev and in builds alike.
    name: 'parsrag-version',
    transformIndexHtml: () => [{ tag: 'meta', attrs: { name: 'parsrag-version', content: appVersion }, injectTo: 'head' }],
  }],
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
      '/settings': localApi,
      '/updates': localApi,
      '/release-notes': localApi,
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
