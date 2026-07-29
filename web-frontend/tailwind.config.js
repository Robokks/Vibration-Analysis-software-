import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

// Single source of truth: read the canonical tokens straight from
// design-tokens/ (never duplicated/edited here) and derive the Tailwind
// theme from it, the same file the Qt app's QSS generator reads.
const tokensPath = path.resolve(
  dirname,
  "../design-tokens/src/nvh_design_tokens/tokens.json",
);
const tokens = JSON.parse(fs.readFileSync(tokensPath, "utf-8"));

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        dark: tokens.color.palettes.dark,
        print: tokens.color.palettes.print,
        graticule: tokens.layout.graticuleColor,
      },
      fontFamily: {
        body: [tokens.type.body, "ui-sans-serif", "system-ui", "sans-serif"],
        display: [tokens.type.display, "ui-sans-serif", "sans-serif"],
        mono: [tokens.type.mono, "ui-monospace", "SFMono-Regular", "monospace"],
      },
      opacity: {
        "graticule-minor": tokens.layout.graticuleMinorAlpha,
      },
      borderWidth: {
        graticule: `${tokens.layout.graticuleStrokeWidth}px`,
      },
    },
  },
  plugins: [],
};
