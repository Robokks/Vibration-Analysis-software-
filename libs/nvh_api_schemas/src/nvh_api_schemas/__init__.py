from nvh_api_schemas.management import FailReasonRollup, PassRateRollup
from nvh_api_schemas.realtime import LiveDcUpdate, LiveTestRunUpdate
from nvh_api_schemas.report import (
    ConsolidatedReportOut,
    CrashNoiseOut,
    DcAnalysisResultOut,
    DetailedReportOut,
    EnvelopeCheckOut,
    GradingSummaryOut,
    HistogramOut,
    MasterSignatureStatsOut,
    NumericTableRowOut,
    OrderSpectrumOut,
    OrderTrackingOut,
    SlippageOut,
    SummaryReportOut,
    SummaryRowOut,
    XChartOut,
)

# Governs the analysis-engine -> nvh_api_schemas report-shape boundary
# (the Consolidated/Detailed/Summary report wire schemas in report.py). This
# is independent of nvh_contract.CONTRACT_VERSION, which governs the
# separate Parquet/DB manifest boundary -- see docs/data-contract.md's
# "Report/API contract versioning" section.
REPORT_SCHEMA_VERSION = "2.0"

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "FailReasonRollup",
    "PassRateRollup",
    "LiveDcUpdate",
    "LiveTestRunUpdate",
    "ConsolidatedReportOut",
    "CrashNoiseOut",
    "DcAnalysisResultOut",
    "DetailedReportOut",
    "EnvelopeCheckOut",
    "GradingSummaryOut",
    "HistogramOut",
    "MasterSignatureStatsOut",
    "NumericTableRowOut",
    "OrderSpectrumOut",
    "OrderTrackingOut",
    "SlippageOut",
    "SummaryReportOut",
    "SummaryRowOut",
    "XChartOut",
]
