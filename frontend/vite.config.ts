import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
// The UI calls /api/*; in dev and preview Vite forwards those to the FastAPI backend, so
// the browser sees a single origin and no CORS setup is needed.
const backend = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";
const proxy = {
  "/api": {
    target: backend,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
};
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
