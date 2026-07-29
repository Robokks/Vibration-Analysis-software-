"""Recursively converts report objects into plain JSON-serializable data.
Report dataclasses mix plain dataclasses, pydantic models (from nvh_contract),
numpy arrays (spectra/traces), and enums — none of which `dataclasses.asdict`
handles on its own when nested together."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {field.name: to_jsonable(getattr(obj, field.name)) for field in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(item) for item in obj]
    return obj
