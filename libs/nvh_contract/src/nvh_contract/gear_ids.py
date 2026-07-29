"""PLC gear_id <-> gear_label lookup. This is a hardware-defined constant of
the PLC boundary, not a business rule, so it's centralized here rather than
duplicated by the simulator and any future LabVIEW-ingestion adapter. No
pydantic model references this -- it's a standalone convenience."""

from __future__ import annotations

GEAR_ID_TO_LABEL: dict[int, str] = {
    0: "N",
    1: "R",
    2: "I",
    3: "II",
    4: "III",
    5: "IV",
    6: "V",
}

GEAR_LABEL_TO_ID: dict[str, int] = {label: gear_id for gear_id, label in GEAR_ID_TO_LABEL.items()}


def gear_label_from_id(gear_id: int) -> str:
    try:
        return GEAR_ID_TO_LABEL[gear_id]
    except KeyError:
        raise ValueError(f"unknown gear_id {gear_id!r}") from None


def gear_id_from_label(gear_label: str) -> int:
    try:
        return GEAR_LABEL_TO_ID[gear_label]
    except KeyError:
        raise ValueError(f"unknown gear_label {gear_label!r}") from None
