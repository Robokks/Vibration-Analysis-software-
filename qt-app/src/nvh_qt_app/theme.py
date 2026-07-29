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

from nvh_design_tokens import load_tokens


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
    """
