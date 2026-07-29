"""Re-exports of the dataclasses/models the report layer composes. No new
fields are introduced here — reports are built entirely from what the
pipeline and data contract already produce."""

from nvh_contract.models import DcRecord, Model, TestRun

from analysis_engine.grading.envelope_check import EnvelopeCheckResult
from analysis_engine.grading.master_builder import MasterSignatureStats
from analysis_engine.pipeline import DcAnalysisResult
from analysis_engine.spc.histogram import HistogramResult
from analysis_engine.spc.xchart import XChartResult

__all__ = [
    "DcRecord",
    "Model",
    "TestRun",
    "EnvelopeCheckResult",
    "MasterSignatureStats",
    "DcAnalysisResult",
    "HistogramResult",
    "XChartResult",
]
