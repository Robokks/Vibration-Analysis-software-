# qt-app

PySide6 Report GUI desktop client. **Master Entry** and **Reports** are
wired to a live [`../web-backend`](../web-backend) FastAPI service
(`api_client.py`, built on `QNetworkAccessManager` so requests never block
the UI thread) and show the real seeded demo dataset — the same data
`../web-frontend` shows, via the same API contract. **Live Display** is
still a placeholder (`TODO:` banner) — it needs a continuous live stream
and nothing in this codebase produces one yet.

Run `../web-backend`'s server first (see its own README, defaults to
`http://127.0.0.1:8000`, matching `api_client.py`'s default) before
launching this app.

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
