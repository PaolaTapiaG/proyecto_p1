import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El arranque normal de Lumora usa `index.py` en el puerto 8000. La vista
// previa aislada sigue pudiendo usar 8011 mediante LUMORA_API_TARGET.
const apiTarget = process.env.LUMORA_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": apiTarget,
      "/health": apiTarget,
      "/media": apiTarget,
    },
  },
});
