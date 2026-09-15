import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    outDir: resolve(__dirname, "../src/hixton/ui/static"),
    emptyOutDir: true,
    sourcemap: false,
  },
});
