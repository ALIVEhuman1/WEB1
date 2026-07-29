import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

// `npm run build` 는 모든 JS/CSS 를 index.html 안에 인라인해
// 인터넷·서버 없이 더블클릭으로 열리는 단일 HTML 파일을 만든다.
export default defineConfig({
  plugins: [viteSingleFile()],
  server: {
    host: true,
    port: 5173,
  },
  build: {
    target: 'esnext',
    assetsInlineLimit: 100000000,
    cssCodeSplit: false,
  },
});
