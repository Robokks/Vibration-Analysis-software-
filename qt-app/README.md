# qt-app

PySide6 scaffold for the NVH Report GUI desktop client. **GUI scaffolding
only — no live data wiring.** Every screen renders placeholder content and
carries a `TODO:` banner explaining what it wires up to once the
corresponding backend phase lands (see `PROGRESS.md` at the repo root for
Phase C–E status). Screens mirror `../web-frontend`'s Live Display / Master
Entry / Reports.

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
