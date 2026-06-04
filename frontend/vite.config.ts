import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + health to the FastAPI backend on :8000 during dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
