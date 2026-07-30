from nvh_api_schemas.catalog import (
    CalibrationOut,
    CalibrationUpdate,
    LimitConfigLimitUpdate,
    LimitConfigThresholdUpdate,
    ParameterCatalogRowOut,
    TableConfigParameterUpdate,
)
from nvh_api_schemas.management import FailReasonRollup, PassRateRollup
from nvh_api_schemas.realtime import LiveDcUpdate, LiveEvent, LiveEventEnvelope, LiveSignalChunk, LiveTestRunUpdate
from nvh_api_schemas.report import (
    CodeResultReportOut,
    CodeResultRowOut,
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
# (the Consolidated/Detailed/Summary/CodeResult report wire schemas in
# report.py). This is independent of nvh_contract.CONTRACT_VERSION, which
# governs the separate Parquet/DB manifest boundary -- see
# docs/data-contract.md's "Report/API contract versioning" section, which
# also spells out the integer-vs-decimal bump convention this version
# establishes (2.0 -> 2.1 is purely additive: new required fields on
# EnvelopeCheckOut, one new schema, no removals).
REPORT_SCHEMA_VERSION = "2.1"

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "FailReasonRollup",
    "PassRateRollup",
    "LiveDcUpdate",
    "LiveEvent",
    "LiveEventEnvelope",
    "LiveSignalChunk",
    "LiveTestRunUpdate",
    "CodeResultReportOut",
    "CodeResultRowOut",
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
    "CalibrationOut",
    "CalibrationUpdate",
    "LimitConfigLimitUpdate",
    "LimitConfigThresholdUpdate",
    "ParameterCatalogRowOut",
    "TableConfigParameterUpdate",
]
