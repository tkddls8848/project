import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // 포트를 고정한다. 기본값에 맡기면 이미 쓰는 포트일 때 조용히 다른 번호로
    // 옮겨가, 저장소가 문서로 약속한 5173과 어긋난다.
    port: 5173,
    strictPort: true,
    proxy: {
      '/ollama': {
        target: 'http://localhost:11434',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/ollama/, ''),
      },
      '/api/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
      },
      '/combiner': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/combiner/, ''),
      },
    },
  },
});
