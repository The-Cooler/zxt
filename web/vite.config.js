import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  // eslint-disable-next-line no-undef
  const env = {
    ...loadEnv(mode, process.cwd(), ''),
    // loadEnv 只读取 env 文件，这里合并容器和命令行注入的环境变量。
    // 这样 Docker Compose 中的 VITE_DOCS_URL 才能生效。
    // eslint-disable-next-line no-undef
    ...process.env
  }
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      proxy: {
        '^/api': {
          target: env.VITE_API_URL || 'http://api:5050',
          changeOrigin: true
        },
        '^/docs': {
          target: env.VITE_DOCS_URL || 'http://localhost:5174',
          changeOrigin: true
        }
      },
      watch: {
        usePolling: true,
        ignored: ['**/node_modules/**', '**/dist/**'],
      },
      host: '0.0.0.0',
    }
  }
})
