import gearGlyphMarkup from "@design-tokens/assets/gear-glyph.svg?raw";

type GearGlyphProps = {
  /** Rotate #gear-left/#gear-right in opposite directions, per the asset's own doc comment. */
  spinning?: boolean;
  /** Fill the wrapper's box (for stamp/watermark use) instead of sizing to text height. */
  fill?: boolean;
  className?: string;
};

/**
 * The app's one signature element (per docs/design-tokens.md): a
 * meshing-gear-tooth glyph used as the live-test indicator, the PASS/FAIL
 * stamp outline, and a print watermark. Colors come from `currentColor`, so
 * this component paints with whatever text color its wrapper sets.
 */
export function GearGlyph({ spinning = false, fill = false, className = "" }: GearGlyphProps) {
  const variantClasses = [spinning && "gear-glyph--spinning", fill && "gear-glyph--fill"]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`gear-glyph ${variantClasses} ${className}`}
      role="img"
      aria-label="Gear mesh glyph"
      dangerouslySetInnerHTML={{ __html: gearGlyphMarkup }}
    />
  );
}
