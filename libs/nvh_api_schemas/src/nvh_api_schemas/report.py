"""Wire schemas for the Consolidated/Detailed/Summary reports. Field shapes
mirror analysis_engine.reports.* and analysis_engine.pipeline.DcAnalysisResult
exactly, so a `to_jsonable(report)` payload from the backend validates here
without transformation, and the Qt client parses the same JSON with the same
classes."""

from __future__ import annotations

from typing import Literal

from nvh_contract.models import DcRecord, Model, TestRun
from pydantic import BaseModel


class OrderSpectrumOut(BaseModel):
    order: list[float]
    magnitude: list[float]


class OrderTrackingOut(BaseModel):
    time_s: list[float]
    magnitude: list[float]


class CrashNoiseOut(BaseModel):
    peak_band_rms: float
    threshold: float
    detected: bool


class SlippageOut(BaseModel):
    min_ratio: float
    dropout_fraction: float
    detected: bool


class EnvelopeCheckOut(BaseModel):
    g_level: int
    ok_flag: bool


class GradingSummaryOut(BaseModel):
    per_stat: dict[str, EnvelopeCheckOut]
    passed: bool


class DcAnalysisResultOut(BaseModel):
    gear_label: str
    direction: str
    parameters: dict[str, float]
    order_spectrum: OrderSpectrumOut
    order_tracking: OrderTrackingOut
    crash_noise: CrashNoiseOut
    slippage: SlippageOut
    grading: GradingSummaryOut | None = None
    fail_reason_codes: list[str] = []
    passed: bool


class ConsolidatedReportOut(BaseModel):
    test_run: TestRun
    dc_record: DcRecord
    model: Model
    result: DcAnalysisResultOut
    stamp: Literal["PASS", "FAIL"]


class MasterSignatureStatsOut(BaseModel):
    mean_value: float
    band_min: float
    band_max: float
    full_scale: float
    trial_count: int


class NumericTableRowOut(BaseModel):
    stat_name: str
    domain: str
    observed_value: float
    master: MasterSignatureStatsOut | None = None
    grading: EnvelopeCheckOut | None = None


class DetailedReportOut(BaseModel):
    consolidated: ConsolidatedReportOut
    numeric_table: list[NumericTableRowOut]


class SummaryRowOut(BaseModel):
    test_run: TestRun
    dc_record: DcRecord
    result: DcAnalysisResultOut


class XChartOut(BaseModel):
    center_line: float
    ucl: float
    lcl: float
    values: list[float]
    out_of_control_indices: list[int]


class HistogramOut(BaseModel):
    bin_edges: list[float]
    counts: list[int]
    normal_pdf_x: list[float]
    normal_pdf_y: list[float]


class SummaryReportOut(BaseModel):
    model_id: str
    gear_label: str
    direction: str
    stat_name: str
    rows: list[SummaryRowOut]
    xchart: XChartOut
    histogram: HistogramOut
