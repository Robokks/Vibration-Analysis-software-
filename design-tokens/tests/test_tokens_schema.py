import re

from nvh_design_tokens import gear_glyph_path, load_tokens

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_load_tokens_returns_expected_top_level_keys():
    tokens = load_tokens()
    assert set(tokens.keys()) == {"schema_version", "color", "type", "layout", "assets"}


def test_all_palettes_have_the_same_color_roles():
    palettes = load_tokens()["color"]["palettes"]
    role_sets = {name: set(roles.keys()) for name, roles in palettes.items()}
    first_roles = next(iter(role_sets.values()))
    for name, roles in role_sets.items():
        assert roles == first_roles, f"palette {name!r} has mismatched roles: {roles} != {first_roles}"


def test_every_color_value_is_a_valid_hex_color():
    palettes = load_tokens()["color"]["palettes"]
    for palette_name, roles in palettes.items():
        for role_name, value in roles.items():
            assert HEX_COLOR_RE.match(value), f"{palette_name}.{role_name} = {value!r} is not #RRGGBB"


def test_type_roles_present():
    type_tokens = load_tokens()["type"]
    assert set(type_tokens.keys()) == {"body", "display", "mono"}
    assert all(isinstance(v, str) and v for v in type_tokens.values())


def test_gear_glyph_asset_exists_on_disk():
    path = gear_glyph_path()
    assert path.exists(), f"gear glyph asset not found at {path}"
    assert path.suffix == ".svg"
