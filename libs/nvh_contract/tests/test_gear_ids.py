import pytest

from nvh_contract.gear_ids import GEAR_ID_TO_LABEL, gear_id_from_label, gear_label_from_id


def test_mapping_covers_neutral_reverse_and_five_forward_gears():
    assert GEAR_ID_TO_LABEL == {0: "N", 1: "R", 2: "I", 3: "II", 4: "III", 5: "IV", 6: "V"}


def test_gear_label_from_id_round_trips_with_gear_id_from_label():
    for gear_id, label in GEAR_ID_TO_LABEL.items():
        assert gear_label_from_id(gear_id) == label
        assert gear_id_from_label(label) == gear_id


def test_gear_label_from_id_returns_none_for_unknown_id():
    # Phase O Bug 3b: symmetric with direction_from_nvh_id. The PLC
    # hot-path (sm.gear_label @property) must not raise on a rogue
    # gear_id like 7 or 99 -- return None so the emission guard can
    # short-circuit cleanly.
    assert gear_label_from_id(7) is None
    assert gear_label_from_id(99) is None
    assert gear_label_from_id(-1) is None


def test_gear_id_from_label_rejects_unknown_label():
    with pytest.raises(ValueError):
        gear_id_from_label("VI")
