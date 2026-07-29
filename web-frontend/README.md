# web-frontend

Vite + React + TypeScript + Tailwind scaffold for the NVH Report GUI web
client. **GUI scaffolding only — no live data wiring.** Every screen renders
placeholder content and carries a `TODO:` banner explaining what it wires up
to once the corresponding backend phase lands (see `PROGRESS.md` at the repo
root for Phase C–E status).

## Design tokens

The Tailwind theme (`tailwind.config.js`) and the gear-glyph asset
(`src/components/GearGlyph.tsx`) are both read directly from
[`../design-tokens/src/nvh_design_tokens/tokens.json`](../design-tokens/src/nvh_design_tokens/tokens.json)
— nothing is hand-copied, so the web app and the Qt app (`../qt-app`) always
render the same palette/type/graticule values. See
[`../docs/design-tokens.md`](../docs/design-tokens.md) for the design
direction.

## Setup

```bash
npm install
npm run dev
```

## Scripts

- `npm run dev` — start the Vite dev server
- `npm run build` — typecheck (`tsc -b`) and build a production bundle
- `npm run typecheck` — typecheck only
- `npm run preview` — preview a production build locally
