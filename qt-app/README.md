# qt-app

PySide6 Report GUI desktop client. All three screens are wired to a live
[`../web-backend`](../web-backend) FastAPI service:
- **Master Entry** / **Reports** — REST via `api_client.py`, built on
  `QNetworkAccessManager` so requests never block the UI thread.
- **Live Display** — streaming signal trace + PASS/FAIL stamp via
  `QWebSocket`, wrapped in `live_client.py` (same async, callback-based
  shape as the REST client). The trace overpaints a rolling buffer on
  top of the existing graticule widget (`widgets/signal_trace.py`).

Both use the same visual language derived from `../design-tokens` and
the same API contract as `../web-frontend`. Run the backend + live
simulator first (see `../web-backend/README.md`, defaults to
`http://127.0.0.1:8000` + ZeroMQ `tcp://127.0.0.1:5555`, matching this
app's own defaults) before launching.

## Design tokens

`theme.py`'s `build_stylesheet()` reads
[`../design-tokens/src/nvh_design_tokens/tokens.json`](../design-tokens/src/nvh_design_tokens/tokens.json)
(via the `nvh_design_tokens` package) and derives a QSS stylesheet from it,
the same way `../web-frontend/tailwind.config.js` derives its Tailwind theme
— so both clients render the same palette/type/graticule values from one
source. `widgets/gear_glyph.py` renders the same gear-glyph SVG asset,
substituting the token color in for the asset's `currentColor` placeholders
at draw time (Qt's SVG renderer has no notion of CSS `currentColor`).

Note: the QSS references the token type family names (IBM Plex Sans/Mono,
Space Grotesk) but doesn't bundle the font files — Qt falls back to a system
font if they aren't installed. Bundling them (`QFontDatabase.addApplicationFont`)
is future work, same as the rest of this scaffold.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../design-tokens -e . pytest
```

## Run

```bash
.venv/bin/nvh-qt-app
# or: .venv/bin/python -m nvh_qt_app
```

## Test

Headless (no display needed — tests force `QT_QPA_PLATFORM=offscreen`):

```bash
.venv/bin/python -m pytest tests -q
```
