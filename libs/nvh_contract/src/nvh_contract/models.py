"""Pydantic models mirroring docs/data-contract.md. These validate rows crossing
the acquisition/analysis boundary (today: the simulator; later: LabVIEW)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Direction(str, Enum):
    RU = "RU"      # Run-up             (PLC nvh_id 0)
    STYD = "STYD"  # Steady state/drive (PLC nvh_id 1)
    STYC = "STYC"  # Steady coast       (PLC nvh_id 2)
    RD = "RD"      # Run-down           (PLC nvh_id 3)
    # PLC nvh_id -1 ("no log") is a transport-layer sentinel, not a domain
    # value, and is intentionally not represented here. Reverse (R)
    # conventionally only logs RU/STYD/RD (no STYC) -- a data/config
    # convention, not enforced by this enum; see Phase B/E.


class Domain(str, Enum):
    TIME = "time"
    SPEED = "speed"


class OverallResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


class Model(BaseModel):
    model_id: str
    model_name: str
    drive_teeth: dict[str, int]
    idler_teeth_1: dict[str, int]
    idler_teeth_2: dict[str, int] = Field(default_factory=dict)
    layshaft_teeth: dict[str, int]
    drive_shaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    layshaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    fdr_teeth: dict[str, int] = Field(default_factory=dict)
    fd_sel: dict[str, str] = Field(default_factory=dict)
    ratios: dict[str, float]


class TestRun(BaseModel):
    test_run_id: str
    model_id: str
    serial_number: str
    operator_id: str | None = None
    shift_number: str | None = None
    repeat_number: int = 1
    line_id: str | None = None
    station_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    overall_result: OverallResult = OverallResult.PENDING


class DcRecord(BaseModel):
    dc_id: str
    test_run_id: str
    gear_label: str
    direction: Direction
    rpm_start: float
    rpm_end: float
    sample_rate_hz: float
    parquet_path: str
    result: OverallResult = OverallResult.PENDING
    fail_reason_codes: list[str] = Field(default_factory=list)


class Channel(BaseModel):
    channel_id: str
    dc_id: str
    channel_name: str
    sensor_type: str | None = None
    units: str
    sensitivity_mv_per_eu: float | None = None
    pregain_db: float = 0.0
    weighting_filter: str = "linear"


class MasterSignature(BaseModel):
    master_id: str
    model_id: str
    gear_label: str
    direction: Direction
    stat_name: str
    domain: Domain
    mean_value: float
    band_min: float
    band_max: float
    full_scale: float
    trial_count: int
    created_at: datetime


class GradingResult(BaseModel):
    dc_id: str
    stat_name: str
    domain: Domain
    g_level: int = Field(ge=1, le=10)
    ok_flag: bool


class SpcPoint(BaseModel):
    serial_number: str
    model_id: str
    gear_label: str
    direction: Direction
    stat_name: str
    value: float
    recorded_at: datetime


class MasterProfile(BaseModel):
    model_id: str
    program_name: str  # e.g. "REVA" -- the real system's "NVH-PROGRAM"
    created_at: datetime


class LimitConfigEntry(BaseModel):
    model_id: str
    program_name: str
    gear_label: str
    direction: Direction
    channel_name: str = "vib_a"
    stat_name: str
    order_number: float | None = None
    limit_low: float
    limit_high: float
    threshold_low: float = 0.0
    threshold_high: float = 0.0
    updated_at: datetime
