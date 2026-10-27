import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  return {
    plugins: [
      vue(),
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia'],
        dts: 'src/auto-imports.d.ts',
      }),
      Components({
        dirs: ['src/components'],
        dts: 'src/components.d.ts',
      }),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@repo-doc-guides': resolve(__dirname, '../../docs/guides'),
      },
    },
    server: {
      fs: {
        allow: [resolve(__dirname), resolve(__dirname, '../../docs/guides')],
      },
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:5800',
          changeOrigin: true,
        },
        '/compliance': {
          target: 'http://127.0.0.1:6311',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/compliance/, ''),
        },
        '/culture': {
          target: 'http://127.0.0.1:6322',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/culture/, ''),
        },
      },
    },
  }
})
