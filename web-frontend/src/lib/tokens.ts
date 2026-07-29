// Re-exports the canonical design tokens for use outside Tailwind class names
// (e.g. inline SVG). Tailwind's own theme (see tailwind.config.js) reads the
// same file directly with Node's fs, independently of this module.
import tokensJson from "@design-tokens/tokens.json";

export type ColorPalette = {
  background: string;
  panel: string;
  secondaryText: string;
  accentPrimary: string;
  accentSecondary: string;
  alarm: string;
  pass: string;
};

export type DesignTokens = {
  schema_version: string;
  color: { palettes: { dark: ColorPalette; print: ColorPalette } };
  type: { body: string; display: string; mono: string };
  layout: {
    graticuleStrokeWidth: number;
    graticuleColor: string;
    graticuleMinorAlpha: number;
  };
  assets: { gearGlyph: string };
};

export const tokens = tokensJson as DesignTokens;
