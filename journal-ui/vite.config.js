import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../dashboard/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("lightweight-charts")) return "tradingview";
          if (id.includes("recharts") || id.includes("d3-")) return "analytics";
          if (id.includes("lucide-react")) return "icons";
          if (id.includes("date-fns")) return "dates";
          if (id.includes("node_modules/react")) return "react";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8421",
      "/healthz": "http://localhost:8421",
    },
  },
});
