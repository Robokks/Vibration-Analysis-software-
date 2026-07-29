"""Canonical design tokens (color, type, layout, signature assets) shared by
the web frontend and the Qt desktop app, so both render the same visual
language from one source instead of hand-duplicated hex values."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

_PACKAGE = "nvh_design_tokens"


def load_tokens() -> dict:
    data = resources.files(_PACKAGE).joinpath("tokens.json").read_text(encoding="utf-8")
    return json.loads(data)


def gear_glyph_path() -> Path:
    """Absolute filesystem path to the signature gear-glyph SVG asset."""
    tokens = load_tokens()
    relative_path = tokens["assets"]["gearGlyph"]
    return Path(str(resources.files(_PACKAGE).joinpath(relative_path)))
