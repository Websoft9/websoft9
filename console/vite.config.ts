import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const gatewayTarget = process.env.WEBSOFT9_DEV_GATEWAY ?? 'http://127.0.0.1:9000'
const portainerTarget = process.env.WEBSOFT9_DEV_PORTAINER ?? 'http://127.0.0.1:9003'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api/': {
        target: gatewayTarget,
        changeOrigin: true,
      },
      '/media/': {
        target: gatewayTarget,
        changeOrigin: true,
      },
      '/w9deployment/': {
        target: portainerTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/w9deployment/, '/'),
      },
      '/w9proxy/': {
        target: gatewayTarget,
        changeOrigin: true,
      },
      '/w9git/': {
        target: gatewayTarget,
        changeOrigin: true,
      },
      '/w9gateway/': {
        target: gatewayTarget,
        changeOrigin: true,
      },
    },
  },
})
