// Typed client for the nvh-web-backend FastAPI service. Interfaces mirror
// nvh_contract.models / nvh_api_schemas.{report,catalog} field-for-field --
// these field names are load-bearing, not a UI-side choice.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type Direction = "RU" | "STYD" | "STYC" | "RD";
export type OverallResult = "PASS" | "FAIL" | "PENDING";

// ---- domain shapes (nvh_contract.models) ----

export interface ModelSummary {
  model_id: string;
  model_name: string;
}

export interface ModelDetail {
  model_id: string;
  model_name: string;
  drive_teeth: Record<string, number>;
  idler_teeth_1: Record<string, number>;
  idler_teeth_2: Record<string, number>;
  layshaft_teeth: Record<string, number>;
  drive_shaft_bearing_roll: Record<string, number>;
  layshaft_bearing_roll: Record<string, number>;
  fdr_teeth: Record<string, number>;
  fd_sel: Record<string, string>;
  ratios: Record<string, number>;
}

export interface MasterProfile {
  model_id: string;
  program_name: string;
  created_at: string;
}

export interface ParameterMaster {
  mean_value: number;
  band_min: number;
  band_max: number;
  full_scale: number;
  trial_count: number;
}

export interface ParameterRow {
  stat_name: string;
  order_number: number | null;
  master: ParameterMaster | null;
  limit_low: number | null;
  limit_high: number | null;
  threshold_low: number | null;
  threshold_high: number | null;
  included_in_table_config: boolean;
}

export interface TestRunSummary {
  test_run_id: string;
  model_id: string;
  serial_number: string;
  operator_id: string | null;
  shift_number: string | null;
  repeat_number: number;
  line_id: string | null;
  station_id: string | null;
  started_at: string;
  finished_at: string | null;
  overall_result: OverallResult;
}

export interface DcRecordSummary {
  dc_id: string;
  test_run_id: string;
  gear_label: string;
  direction: Direction;
  rpm_start: number;
  rpm_end: number;
  sample_rate_hz: number;
  parquet_path: string;
  result: OverallResult;
  fail_reason_codes: string[];
}

export interface TestRunDetail {
  test_run: TestRunSummary;
  dc_records: DcRecordSummary[];
}

// ---- report shapes (nvh_api_schemas.report) ----

export interface OrderSpectrum {
  order: number[];
  magnitude: number[];
}

export interface OrderTracking {
  time_s: number[];
  magnitude: number[];
}

export interface CrashNoise {
  peak_band_rms: number;
  threshold: number;
  detected: boolean;
}

export interface Slippage {
  min_ratio: number;
  dropout_fraction: number;
  detected: boolean;
}

export interface EnvelopeCheck {
  g_level: number;
  ok_flag: boolean;
  low: number;
  high: number;
}

export interface GradingSummary {
  per_stat: Record<string, EnvelopeCheck>;
  passed: boolean;
}

export interface DcAnalysisResult {
  gear_label: string;
  direction: Direction;
  parameters: Record<string, number>;
  order_spectrum: OrderSpectrum;
  order_tracking: OrderTracking;
  crash_noise: CrashNoise;
  slippage: Slippage;
  grading: GradingSummary | null;
  fail_reason_codes: string[];
  passed: boolean;
}

export interface ConsolidatedReport {
  test_run: TestRunSummary;
  dc_record: DcRecordSummary;
  model: ModelDetail;
  result: DcAnalysisResult;
  stamp: "PASS" | "FAIL";
}

export interface NumericTableRow {
  stat_name: string;
  domain: string;
  observed_value: number;
  master: ParameterMaster | null;
  grading: EnvelopeCheck | null;
}

export interface DetailedReport {
  consolidated: ConsolidatedReport;
  numeric_table: NumericTableRow[];
}

export interface CodeResultRow {
  step: number;
  gear_direction: string;
  channel_name: string;
  parameter: string;
  orders: number | null;
  low: number;
  high: number;
  actual: number;
  unit: string;
  ok_flag: boolean;
}

export interface CodeResultReport {
  rows: CodeResultRow[];
}

export interface XChart {
  center_line: number;
  ucl: number;
  lcl: number;
  values: number[];
  out_of_control_indices: number[];
}

export interface Histogram {
  bin_edges: number[];
  counts: number[];
  normal_pdf_x: number[];
  normal_pdf_y: number[];
}

export interface SummaryRow {
  test_run: TestRunSummary;
  dc_record: DcRecordSummary;
  result: DcAnalysisResult;
}

export interface SummaryReport {
  model_id: string;
  gear_label: string;
  direction: string;
  stat_name: string;
  rows: SummaryRow[];
  xchart: XChart;
  histogram: Histogram;
}

// ---- fetch wrapper ----

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly url: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value);
  }

  let response: Response;
  try {
    response = await fetch(url.toString());
  } catch {
    throw new ApiError(0, url.toString(), `Network error reaching ${path} (is the backend running?)`);
  }
  if (!response.ok) {
    throw new ApiError(response.status, url.toString(), `${path} responded ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

const seg = encodeURIComponent;

export const api = {
  health: () => getJson<{ status: string }>("/health"),
  listModels: () => getJson<ModelSummary[]>("/models"),
  getModel: (modelId: string) => getJson<ModelDetail>(`/models/${seg(modelId)}`),
  listPrograms: (modelId: string) => getJson<MasterProfile[]>(`/models/${seg(modelId)}/programs`),
  listParameters: (
    modelId: string,
    programName: string,
    opts: { gearLabel: string; direction: string; channelName?: string },
  ) =>
    getJson<ParameterRow[]>(`/models/${seg(modelId)}/programs/${seg(programName)}/parameters`, {
      gear_label: opts.gearLabel,
      direction: opts.direction,
      channel_name: opts.channelName ?? "vib_a",
    }),
  listTestRuns: (modelId?: string) => getJson<TestRunSummary[]>("/test-runs", { model_id: modelId }),
  getTestRun: (testRunId: string) => getJson<TestRunDetail>(`/test-runs/${seg(testRunId)}`),
  getConsolidatedReport: (dcId: string, programName?: string) =>
    getJson<ConsolidatedReport>(`/dc-records/${seg(dcId)}/reports/consolidated`, { program_name: programName }),
  getDetailedReport: (dcId: string, programName?: string) =>
    getJson<DetailedReport>(`/dc-records/${seg(dcId)}/reports/detailed`, { program_name: programName }),
  getCodeResultReport: (dcId: string, programName?: string) =>
    getJson<CodeResultReport>(`/dc-records/${seg(dcId)}/reports/code-result`, { program_name: programName }),
  getSummaryReport: (
    modelId: string,
    opts: { gearLabel: string; direction: string; statName: string; programName?: string; channelName?: string },
  ) =>
    getJson<SummaryReport>(`/models/${seg(modelId)}/summary`, {
      gear_label: opts.gearLabel,
      direction: opts.direction,
      stat_name: opts.statName,
      program_name: opts.programName,
      channel_name: opts.channelName ?? "vib_a",
    }),
};
