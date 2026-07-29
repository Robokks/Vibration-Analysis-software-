# Design Tokens

The canonical source of truth for color, typography, layout, and the
signature gear-glyph asset is
[`design-tokens/src/nvh_design_tokens/tokens.json`](../design-tokens/src/nvh_design_tokens/tokens.json),
loaded via `nvh_design_tokens.load_tokens()`.

Every renderer — the (future) web frontend's Tailwind theme, the (future) Qt
desktop app's QSS stylesheet, and the backend's PDF/print export — derives its
colors and fonts from this one file rather than hand-duplicating hex values.
See the package's `pyproject.toml` and tests for the schema it's validated
against (every palette has the same set of color roles, every value is a
`#RRGGBB` hex string).

Design direction, for context: grounded in the actual subject — a vibration/
order analyzer for gearboxes — rather than a generic dashboard look. A cool
graphite background with a dual-trace phosphor accent (amber/cyan, echoing
real spectrum-analyzer dual-channel displays), IBM Plex Mono for every number
in the UI so columns stay aligned, an oscilloscope-graticule grid for plot
areas instead of soft dashboard cards, and a meshing gear-tooth glyph as the
one signature element (live-test indicator, PASS/FAIL stamp outline, and
print watermark).
