# web-frontend

Vite + React + TypeScript + Tailwind Report GUI web client. All three
screens are wired to a live [`../web-backend`](../web-backend) FastAPI
service:
- **Master Entry** / **Reports** — real gear teeth, master signatures,
  limit configs, and Consolidated/Detailed/Summary/Code-Result reports
  from the seeded demo dataset via REST (`src/lib/api.ts`).
- **Live Display** — real streaming signal trace + PASS/FAIL stamp via a
  WebSocket to `/live/ws` (`src/lib/useLiveEvents.ts`), which the backend
  relays from `../web-backend/scripts/live_simulator.py`'s ZeroMQ
  producer.

Run the backend + simulator first (see `../web-backend/README.md`), then
`npm run dev` here. Set `VITE_API_BASE_URL` (defaults to
`http://localhost:8000`, see `.env.development`) if the backend runs
somewhere else — the WebSocket URL is derived from it automatically.

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
