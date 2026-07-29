# web-frontend

Vite + React + TypeScript + Tailwind Report GUI web client. **Master Entry**
and **Reports** are wired to a live [`../web-backend`](../web-backend)
FastAPI service (`src/lib/api.ts`) and show the real seeded demo dataset
(one model/program/gear/direction, 3 test-run scenarios). **Live Display**
is still a placeholder (`TODO:` banner) — it needs a continuous live stream
and nothing in this codebase produces one yet.

Run `../web-backend`'s server first (see its own README), then `npm run
dev` here — set `VITE_API_BASE_URL` (defaults to `http://localhost:8000`,
see `.env.development`) if the backend runs somewhere else.

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
