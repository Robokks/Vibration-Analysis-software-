import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

// The Tailwind theme and the app shell both read design tokens straight out
// of design-tokens/ (see tailwind.config.js and src/lib/tokens.ts) rather than
// duplicating values here. Vite's dev server only serves files inside the
// project root by default, so `fs.allow` is widened to the repo root to let
// those cross-package imports (tokens.json, gear-glyph.svg) resolve in dev.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@design-tokens": path.resolve(dirname, "../design-tokens/src/nvh_design_tokens"),
    },
  },
  server: {
    fs: {
      allow: [path.resolve(dirname, "..")],
    },
  },
});
