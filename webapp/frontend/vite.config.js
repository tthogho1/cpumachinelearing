import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to dist/, which app.py serves as static files in production.
// In dev, `npm run dev` runs its own server and proxies /api calls to Flask on :5000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
