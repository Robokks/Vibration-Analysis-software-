"""SVG glyphs for the Live Display top toolbar. Each icon is a small
stroked line-drawing designed to sit next to the oscilloscope-graticule
aesthetic the rest of the app uses -- 24x24 viewBox, 1.5px stroke, single
color drawn from the design tokens (accentSecondary by default).

Rendered through QSvgRenderer at whatever pixmap size the caller asks for
(the toolbar uses 24px; a larger detail view could ask for 48px without
any pixel-scaling artifacts). No external asset files -- the glyphs are
kept inline so the app stays self-contained and the icon set can be
themed via load_tokens() without touching disk."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_COLOR_MARKER = "__STROKE__"

# Each SVG uses __STROKE__ as a placeholder that the renderer replaces
# with an actual hex color at render time -- lets one glyph serve multiple
# palettes (dark/print) without duplicating markup. `fill="none"` +
# `stroke-linecap="round"` matches the graticule's stroke conventions.
_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="' + _COLOR_MARKER + '" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round">'
)
_TAIL = "</svg>"


def _svg(body: str) -> str:
    return _HEAD + body + _TAIL


_GLYPHS: dict[str, str] = {
    # Arrow entering a rectangle -- classic "log in" motif.
    "login": _svg(
        '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>'
        '<polyline points="10 17 15 12 10 7"/>'
        '<line x1="15" y1="12" x2="3" y2="12"/>'
    ),
    # Three horizontal sliders with dots at different positions -- audio
    # /oscilloscope calibration sliders.
    "calibration": _svg(
        '<line x1="4" y1="6" x2="20" y2="6"/>'
        '<line x1="4" y1="12" x2="20" y2="12"/>'
        '<line x1="4" y1="18" x2="20" y2="18"/>'
        '<circle cx="8" cy="6" r="2"/>'
        '<circle cx="16" cy="12" r="2"/>'
        '<circle cx="10" cy="18" r="2"/>'
    ),
    # 8-tooth gear -- system configuration.
    "system_config": _svg(
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1'
        'M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>'
    ),
    # Document with data lines -- detailed report.
    "d_report": _svg(
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="8" y1="13" x2="16" y2="13"/>'
        '<line x1="8" y1="17" x2="16" y2="17"/>'
        '<line x1="8" y1="9" x2="10" y2="9"/>'
    ),
    # Document with bar chart -- summary report.
    "summary_report": _svg(
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="8" y1="17" x2="8" y2="13"/>'
        '<line x1="12" y1="17" x2="12" y2="11"/>'
        '<line x1="16" y1="17" x2="16" y2="14"/>'
    ),
    # Circle with concentric ring + center dot -- master signature marker.
    "master": _svg(
        '<circle cx="12" cy="12" r="9"/>'
        '<circle cx="12" cy="12" r="5"/>'
        '<circle cx="12" cy="12" r="1.2" fill="' + _COLOR_MARKER + '"/>'
    ),
    # Master glyph with a small gear tucked in the corner -- master setup.
    "master_setup": _svg(
        '<circle cx="10" cy="12" r="7"/>'
        '<circle cx="10" cy="12" r="1" fill="' + _COLOR_MARKER + '"/>'
        '<circle cx="18" cy="6" r="2.4"/>'
        '<path d="M18 3v1.2M18 7.8v1.2M15 6h1.2M19.8 6H21"/>'
    ),
    # 3x3 grid -- table config.
    "table_config": _svg(
        '<rect x="3" y="3" width="18" height="18" rx="1"/>'
        '<line x1="3" y1="9" x2="21" y2="9"/>'
        '<line x1="3" y1="15" x2="21" y2="15"/>'
        '<line x1="9" y1="3" x2="9" y2="21"/>'
        '<line x1="15" y1="3" x2="15" y2="21"/>'
    ),
    # Gauge arc with needle -- limit config (LIMIT/THRESHOLD bounds).
    "limit_config": _svg(
        '<path d="M4 18a8 8 0 0 1 16 0"/>'
        '<line x1="12" y1="18" x2="16.5" y2="9"/>'
        '<circle cx="12" cy="18" r="1.2" fill="' + _COLOR_MARKER + '"/>'
        '<line x1="5" y1="18" x2="4" y2="18"/>'
        '<line x1="19" y1="18" x2="20" y2="18"/>'
    ),
}


def make_icon(name: str, color: str, size: int = 24) -> QIcon:
    """Render one of the named glyphs to a QIcon at the given color/size.
    Color is a hex string ("#3ECF8E") interpolated into the SVG stroke.
    Anti-aliased so the icons look crisp at any size Qt asks the
    QToolButton to paint them (e.g. 48px in a large-icon view)."""
    if name not in _GLYPHS:
        raise KeyError(f"unknown icon {name!r}; known: {sorted(_GLYPHS)}")
    svg_bytes = _GLYPHS[name].replace(_COLOR_MARKER, color).encode("utf-8")

    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


ICON_NAMES: tuple[str, ...] = tuple(_GLYPHS.keys())
