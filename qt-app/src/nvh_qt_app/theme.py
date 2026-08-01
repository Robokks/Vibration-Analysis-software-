"""Qt stylesheet (QSS) derived from the canonical design tokens.

Reads ``design-tokens/src/nvh_design_tokens/tokens.json`` through the
``nvh_design_tokens`` package (never duplicated/edited here) and builds a QSS
string from it, the same way the web frontend's Tailwind theme
(``web-frontend/tailwind.config.js``) derives its theme from the same file —
so both clients render the same visual language from one source.

QSS has no custom-property/variable mechanism, so token values are baked
into the stylesheet text at build time via simple string formatting. Widget
*type* selectors (``Panel``, ``SectionTitle``, ...) target the semantic
QWidget/QLabel subclasses in ``widgets/``, rather than relying on
``#objectName`` or dynamic-property selectors, since Qt's style engine
matches selectors against a widget's actual class name.
"""

from __future__ import annotations

from pathlib import Path

from nvh_design_tokens import load_tokens

# Arrow SVGs are written next to this module so QSS can reference them
# via a file:// URL. Generated per-palette on demand so the arrow color
# tracks the theme.
_ASSETS_DIR = Path(__file__).parent / "assets"
_ARROW_UP_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="7" '
    'viewBox="0 0 10 7"><polygon points="5,1 9,6 1,6" fill="{color}"/></svg>'
)
_ARROW_DOWN_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="7" '
    'viewBox="0 0 10 7"><polygon points="5,6 9,1 1,1" fill="{color}"/></svg>'
)


def _write_arrow_svgs(color_hex: str) -> tuple[str, str]:
    """Write arrow_up_<palette>.svg + arrow_down_<palette>.svg with the
    given color baked in, return (up_path_uri, down_path_uri) as
    file:// URLs suitable for QSS `image:` properties. Overwrites on
    every call so palette flips take effect immediately."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    # Slug based on the hex so switching between palettes doesn't step
    # on itself; also lets both dark + light SVGs coexist on disk.
    slug = color_hex.lstrip("#").lower()
    up_path = _ASSETS_DIR / f"arrow_up_{slug}.svg"
    down_path = _ASSETS_DIR / f"arrow_down_{slug}.svg"
    up_path.write_text(_ARROW_UP_TEMPLATE.format(color=color_hex))
    down_path.write_text(_ARROW_DOWN_TEMPLATE.format(color=color_hex))
    # Qt QSS accepts plain absolute paths in the url("...") of the
    # image: property; the file:// scheme prefix is unnecessary and
    # sometimes not recognized by the QSS parser depending on Qt
    # version. Use forward slashes on all platforms.
    return up_path.resolve().as_posix(), down_path.resolve().as_posix()


def build_stylesheet(palette_name: str = "dark") -> str:
    tokens = load_tokens()
    palette = tokens["color"]["palettes"][palette_name]
    layout = tokens["layout"]
    fonts = tokens["type"]

    background = palette["background"]
    panel = palette["panel"]
    secondary_text = palette["secondaryText"]
    accent_primary = palette["accentPrimary"]
    accent_secondary = palette["accentSecondary"]
    alarm = palette["alarm"]
    pass_color = palette["pass"]
    graticule = layout["graticuleColor"]
    stroke = layout["graticuleStrokeWidth"]
    # URL-encoded hex for use inside data:image/svg+xml URIs -- Qt's
    # QSS parser reads the whole string but `#` is the URL fragment
    # marker, so we escape it. Palette-aware so the arrows recolor
    # correctly on the dark/light theme flip.
    # Concrete SVG arrow assets on disk for the QSS image: property.
    # QSS's data-URI SVG support is unreliable across Qt versions/plugin
    # loadouts, but file:// URLs to real SVG files render consistently
    # via the QtSvg image plugin.
    arrow_up_url, arrow_down_url = _write_arrow_svgs(accent_secondary)

    return f"""
    QWidget {{
        background-color: {background};
        color: {secondary_text};
        font-family: "{fonts["body"]}";
        font-size: 13px;
    }}

    HeaderBar {{
        background-color: {panel};
        border: none;
        border-bottom: {stroke}px solid {graticule};
    }}

    AppTitle {{
        color: #FFFFFF;
        font-family: "{fonts["display"]}";
        font-size: 16px;
        font-weight: bold;
    }}

    AppSubtitle {{
        color: {secondary_text};
        font-family: "{fonts["mono"]}";
        font-size: 11px;
    }}

    NavButton {{
        background: transparent;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        color: {secondary_text};
        font-family: "{fonts["display"]}";
        font-size: 13px;
    }}

    NavButton:hover {{
        color: {accent_secondary};
    }}

    NavButton:checked {{
        background-color: {background};
        color: {accent_primary};
    }}

    QPushButton#ThemeToggle {{
        background: transparent;
        border: {stroke}px solid {graticule};
        border-radius: 4px;
        padding: 4px 12px;
        margin-left: 12px;
        color: {secondary_text};
        font-family: "{fonts["mono"]}";
        font-size: 11px;
    }}

    QPushButton#ThemeToggle:hover {{
        color: {accent_secondary};
        border-color: {accent_secondary};
    }}

    QPushButton#FreqSettingsButton {{
        background: transparent;
        border: none;
        padding: 4px 10px;
        color: {accent_secondary};
        font-family: "{fonts["mono"]}";
        font-size: 11px;
    }}

    QPushButton#FreqSettingsButton:hover {{
        color: {accent_primary};
    }}

    TodoBanner {{
        background-color: {panel};
        border: 1px solid {accent_primary};
        border-radius: 4px;
        color: {accent_primary};
    }}

    TodoBanner MonoLabel {{
        color: {accent_primary};
    }}

    Panel {{
        background-color: {panel};
        border: {stroke}px solid {graticule};
        border-radius: 4px;
    }}

    Chip {{
        background-color: {background};
        border: {stroke}px solid {graticule};
        border-radius: 4px;
        padding: 4px 8px;
        font-family: "{fonts["mono"]}";
        font-size: 11px;
    }}

    SectionTitle {{
        color: {accent_primary};
        font-family: "{fonts["display"]}";
        font-size: 12px;
        font-weight: bold;
    }}

    MonoLabel {{
        font-family: "{fonts["mono"]}";
        font-size: 12px;
        color: {secondary_text};
    }}

    ValueLabel {{
        font-family: "{fonts["mono"]}";
        font-size: 14px;
        color: #FFFFFF;
    }}

    PassLabel {{
        color: {pass_color};
        font-family: "{fonts["display"]}";
        font-weight: bold;
    }}

    AlarmLabel {{
        color: {alarm};
        font-family: "{fonts["display"]}";
        font-weight: bold;
    }}

    QTableWidget {{
        background-color: {panel};
        gridline-color: {graticule};
        font-family: "{fonts["mono"]}";
        font-size: 11px;
        border: none;
    }}

    QHeaderView::section {{
        background-color: {background};
        color: {secondary_text};
        font-family: "{fonts["mono"]}";
        padding: 4px;
        border: none;
        border-bottom: {stroke}px solid {graticule};
    }}

    QTabWidget::pane {{
        background-color: {panel};
        border: {stroke}px solid {graticule};
        border-radius: 4px;
    }}

    QTabBar::tab {{
        background: transparent;
        color: {secondary_text};
        font-family: "{fonts["display"]}";
        padding: 8px 16px;
    }}

    QTabBar::tab:selected {{
        background-color: {panel};
        color: {accent_primary};
    }}

    /* ---- Form controls (used by PLOT SETUP dialog + Calibration screen) ---- */

    QDialog {{
        background-color: {background};
    }}

    QGroupBox {{
        background-color: {panel};
        border: {stroke}px solid {graticule};
        border-radius: 4px;
        margin-top: 14px;
        padding-top: 14px;
        color: {accent_primary};
        font-family: "{fonts["display"]}";
        font-size: 11px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: {accent_primary};
    }}

    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
        background-color: {background};
        color: #FFFFFF;
        border: {stroke}px solid {graticule};
        border-radius: 3px;
        padding: 3px 6px;
        font-family: "{fonts["mono"]}";
        font-size: 12px;
        selection-background-color: {accent_secondary};
        selection-color: {background};
    }}

    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {accent_secondary};
    }}

    /* Spinbox up/down buttons -- give them a visible plate + real
       arrow SVGs generated on disk with the palette's accent color
       baked in. Both dark + light themes get correctly-colored
       arrows this way. */
    QDoubleSpinBox, QSpinBox {{
        padding-right: 22px;
    }}

    QDoubleSpinBox::up-button, QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 20px;
        height: 12px;
        border-left: {stroke}px solid {graticule};
        border-bottom: {stroke}px solid {graticule};
        background-color: {panel};
    }}

    QDoubleSpinBox::down-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 20px;
        height: 12px;
        border-left: {stroke}px solid {graticule};
        background-color: {panel};
    }}

    QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
    QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
        background-color: {background};
    }}

    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
        image: url("{arrow_up_url}");
        width: 10px;
        height: 7px;
    }}

    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
        image: url("{arrow_down_url}");
        width: 10px;
        height: 7px;
    }}

    QComboBox::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 22px;
        border-left: {stroke}px solid {graticule};
        background: transparent;
    }}

    QComboBox::drop-down:hover {{
        background-color: {background};
    }}

    QComboBox::down-arrow {{
        image: url("{arrow_down_url}");
        width: 10px;
        height: 7px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {panel};
        color: #FFFFFF;
        border: {stroke}px solid {graticule};
        selection-background-color: {accent_secondary};
        selection-color: {background};
        padding: 2px;
    }}

    QCheckBox {{
        color: {secondary_text};
        font-family: "{fonts["mono"]}";
        font-size: 12px;
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: {stroke}px solid {graticule};
        border-radius: 2px;
        background-color: {background};
    }}

    QCheckBox::indicator:checked {{
        background-color: {accent_secondary};
        border-color: {accent_secondary};
    }}

    QFormLayout {{
        spacing: 8px;
    }}

    QDialogButtonBox QPushButton {{
        background-color: {panel};
        color: #FFFFFF;
        border: {stroke}px solid {graticule};
        border-radius: 3px;
        padding: 5px 16px;
        font-family: "{fonts["display"]}";
        font-size: 12px;
        min-width: 70px;
    }}

    QDialogButtonBox QPushButton:hover {{
        border-color: {accent_secondary};
        color: {accent_secondary};
    }}

    QDialogButtonBox QPushButton:default {{
        background-color: {accent_secondary};
        color: {background};
        border-color: {accent_secondary};
    }}

    QDialogButtonBox QPushButton:default:hover {{
        background-color: {accent_primary};
        border-color: {accent_primary};
        color: {background};
    }}

    QPushButton#CalibrationSave {{
        background-color: {accent_secondary};
        color: {background};
        border: none;
        border-radius: 3px;
        padding: 6px 20px;
        font-family: "{fonts["display"]}";
        font-size: 12px;
        font-weight: bold;
    }}

    QPushButton#CalibrationSave:hover {{
        background-color: {accent_primary};
    }}
    """
