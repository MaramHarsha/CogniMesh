import { defineConfig, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only auth headers injected by the proxy so the browser bundle never
// carries credentials. These match the development header auth used by the
// CogniMesh control-plane services.
const DEV_AUTH_HEADERS: Record<string, string> = {
  'X-CogniMesh-Actor': 'console',
  'X-CogniMesh-Roles': 'platform_admin',
  'X-CogniMesh-Purpose': 'metadata_administration',
}

const REGISTRY_TARGET = process.env.COGNIMESH_OBJECT_REGISTRY_URL ?? 'http://127.0.0.1:8000'
const QUERY_TARGET = process.env.COGNIMESH_QUERY_SERVICE_URL ?? 'http://127.0.0.1:8060'

const configureAuth: ProxyOptions['configure'] = (proxy) => {
  proxy.on('proxyReq', (proxyReq) => {
    for (const [key, value] of Object.entries(DEV_AUTH_HEADERS)) {
      proxyReq.setHeader(key, value)
    }
  })
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/registry': {
        target: REGISTRY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/registry/, ''),
        configure: configureAuth,
      },
      '/api/query': {
        target: QUERY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/query/, ''),
        configure: configureAuth,
      },
    },
  },
})
