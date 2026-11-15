import { defineConfig, loadEnv } from 'vite';

// Optional dev proxy. Set BACKEND_PROXY_TARGET in .env (e.g. a teammate's ngrok URL) and VITE_API_URL=/backend:
// the browser then calls localhost:5173/backend/..., and Vite forwards to the target server-side.
// This avoids CORS and ngrok's browser-warning page (Vite adds the ngrok-skip-browser-warning header).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.BACKEND_PROXY_TARGET;
  return {
    esbuild: { jsx: 'automatic' },
    server: target ? {
      proxy: {
        '/backend': {
          target,
          changeOrigin: true,
          secure: true,
          rewrite: (p) => p.replace(/^\/backend/, ''),
          headers: { 'ngrok-skip-browser-warning': 'true' },
        },
      },
    } : undefined,
  };
});
