import { useEffect, useState } from "react";
import { GearGlyph } from "../components/GearGlyph";
import { AsyncSection } from "../components/AsyncSection";
import { DemoDataNote } from "../components/DemoDataNote";
import { Panel, SectionTitle } from "../components/Panel";
import {
  api,
  type CodeResultRow,
  type ConsolidatedReport,
  type DetailedReport,
  type SummaryReport,
} from "../lib/api";
import { useApiResource } from "../lib/useApi";

// Same demo-dataset scoping story as MasterEntry.tsx -- one model/program/
// gear/direction exists today, so these are hardcoded rather than selected.
const MODEL_ID = "MODEL-A";
const PROGRAM_NAME = "REVA";
const GEAR_LABEL = "R";
const DIRECTION = "RU";
const SUMMARY_STAT_NAME = "RMS Avg";

const REPORT_TABS = ["Consolidated", "Detailed", "Summary", "Code-Result"] as const;
type ReportTab = (typeof REPORT_TABS)[number];

function StampPreview({ result }: { result: "PASS" | "FAIL" }) {
  const color = result === "PASS" ? "text-dark-pass" : "text-dark-alarm";
  return (
    <div className={`relative inline-flex h-24 w-32 items-center justify-center ${color}`}>
      <GearGlyph fill className="absolute inset-0 opacity-50" />
      <span className="font-display text-xl font-bold tracking-widest">{result}</span>
    </div>
  );
}

function ConsolidatedView({ report }: { report: ConsolidatedReport }) {
  return (
    <div>
      <div className="mb-6 flex items-center gap-8">
        <StampPreview result={report.stamp} />
        <div className="font-mono text-xs text-dark-secondaryText">
          <div>
            gear <span className="text-white">{report.result.gear_label}</span> / {report.result.direction}
          </div>
          <div>
            crash noise: {report.result.crash_noise.detected ? "DETECTED" : "clear"} (peak{" "}
            {report.result.crash_noise.peak_band_rms.toPrecision(3)} / threshold{" "}
            {report.result.crash_noise.threshold})
          </div>
          <div>
            slippage: {report.result.slippage.detected ? "DETECTED" : "clear"} (min ratio{" "}
            {report.result.slippage.min_ratio.toPrecision(3)})
          </div>
          {report.result.fail_reason_codes.length > 0 && (
            <div className="text-dark-alarm">fail reasons: {report.result.fail_reason_codes.join(", ")}</div>
          )}
        </div>
      </div>
      {/* order_spectrum/order_tracking are array time-series -- no charting
          library in this pass (same reasoning as Live Display's deferred
          live stream), shown as a point-count line in the existing
          graticule visual language instead of a plotted chart. */}
      <div className="graticule-bg mb-2 h-40 rounded border border-graticule" />
      <p className="font-mono text-xs text-dark-secondaryText">
        order spectrum / order tracking plotting deferred ({report.result.order_spectrum.order.length} spectrum
        points, {report.result.order_tracking.time_s.length} tracking samples available)
      </p>
    </div>
  );
}

function DetailedView({ report }: { report: DetailedReport }) {
  return (
    <table className="w-full border-collapse font-mono text-xs">
      <thead>
        <tr className="text-left text-dark-secondaryText">
          <th className="border-b border-graticule pb-2 pr-4">Stat</th>
          <th className="border-b border-graticule pb-2 pr-4">Domain</th>
          <th className="border-b border-graticule pb-2 pr-4">Observed</th>
          <th className="border-b border-graticule pb-2 pr-4">Master mean</th>
          <th className="border-b border-graticule pb-2 pr-4">G-level</th>
          <th className="border-b border-graticule pb-2">OK/NOK</th>
        </tr>
      </thead>
      <tbody>
        {report.numeric_table.map((row) => (
          <tr key={row.stat_name}>
            <td className="border-b border-graticule/40 py-2 pr-4 text-white">{row.stat_name}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.domain}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.observed_value.toPrecision(4)}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">
              {row.master ? row.master.mean_value.toPrecision(4) : "—"}
            </td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.grading?.g_level ?? "—"}</td>
            <td
              className={`border-b border-graticule/40 py-2 ${
                row.grading ? (row.grading.ok_flag ? "text-dark-pass" : "text-dark-alarm") : ""
              }`}
            >
              {row.grading ? (row.grading.ok_flag ? "OK" : "NOK") : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SummaryView({ report }: { report: SummaryReport }) {
  return (
    <div>
      <p className="mb-4 font-mono text-xs text-dark-secondaryText">
        {report.stat_name} across {report.rows.length} test run{report.rows.length === 1 ? "" : "s"} for gear{" "}
        {report.gear_label}/{report.direction}
      </p>
      {/* X-chart/histogram are plotted-chart data -- no charting library in
          this pass, same reasoning as ConsolidatedView above. Shown as
          numeric summaries instead. */}
      <div className="mb-4 grid grid-cols-3 gap-4 font-mono text-xs">
        <div className="rounded border border-graticule p-3">
          <div className="text-dark-secondaryText">Center line</div>
          <div className="text-white">{report.xchart.center_line.toPrecision(4)}</div>
        </div>
        <div className="rounded border border-graticule p-3">
          <div className="text-dark-secondaryText">UCL</div>
          <div className="text-white">{report.xchart.ucl.toPrecision(4)}</div>
        </div>
        <div className="rounded border border-graticule p-3">
          <div className="text-dark-secondaryText">LCL</div>
          <div className="text-white">{report.xchart.lcl.toPrecision(4)}</div>
        </div>
      </div>
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="text-left text-dark-secondaryText">
            <th className="border-b border-graticule pb-2 pr-4">Serial number</th>
            <th className="border-b border-graticule pb-2">Value</th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row, index) => (
            <tr key={row.test_run.test_run_id}>
              <td className="border-b border-graticule/40 py-2 pr-4 text-white">{row.test_run.serial_number}</td>
              <td
                className={`border-b border-graticule/40 py-2 ${
                  report.xchart.out_of_control_indices.includes(index) ? "text-dark-alarm" : ""
                }`}
              >
                {report.xchart.values[index]?.toPrecision(4) ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CodeResultTable({ rows }: { rows: CodeResultRow[] }) {
  return (
    <table className="w-full border-collapse font-mono text-xs">
      <thead>
        <tr className="text-left text-dark-secondaryText">
          <th className="border-b border-graticule pb-2 pr-4">Step</th>
          <th className="border-b border-graticule pb-2 pr-4">Gear/Direction</th>
          <th className="border-b border-graticule pb-2 pr-4">Channel</th>
          <th className="border-b border-graticule pb-2 pr-4">Parameter</th>
          <th className="border-b border-graticule pb-2 pr-4">Orders</th>
          <th className="border-b border-graticule pb-2 pr-4">Low</th>
          <th className="border-b border-graticule pb-2 pr-4">Actual</th>
          <th className="border-b border-graticule pb-2 pr-4">High</th>
          <th className="border-b border-graticule pb-2 pr-4">Unit</th>
          <th className="border-b border-graticule pb-2">OK/NOK</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.step}-${row.parameter}`}>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.step}</td>
            <td className="border-b border-graticule/40 py-2 pr-4 text-white">{row.gear_direction}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.channel_name}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.parameter}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">
              {row.orders !== null ? row.orders.toPrecision(4) : "—"}
            </td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.low.toPrecision(4)}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.actual.toPrecision(4)}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.high.toPrecision(4)}</td>
            <td className="border-b border-graticule/40 py-2 pr-4">{row.unit}</td>
            <td
              className={`border-b border-graticule/40 py-2 ${row.ok_flag ? "text-dark-pass" : "text-dark-alarm"}`}
            >
              {row.ok_flag ? "OK" : "NOK"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConsolidatedTab({ dcId }: { dcId: string }) {
  const state = useApiResource(() => api.getConsolidatedReport(dcId, PROGRAM_NAME), [dcId]);
  return <AsyncSection state={state}>{(report) => <ConsolidatedView report={report} />}</AsyncSection>;
}

function DetailedTab({ dcId }: { dcId: string }) {
  const state = useApiResource(() => api.getDetailedReport(dcId, PROGRAM_NAME), [dcId]);
  return <AsyncSection state={state}>{(report) => <DetailedView report={report} />}</AsyncSection>;
}

function SummaryTab() {
  const state = useApiResource(
    () =>
      api.getSummaryReport(MODEL_ID, {
        gearLabel: GEAR_LABEL,
        direction: DIRECTION,
        statName: SUMMARY_STAT_NAME,
        programName: PROGRAM_NAME,
      }),
    [MODEL_ID, GEAR_LABEL, DIRECTION, SUMMARY_STAT_NAME],
  );
  return <AsyncSection state={state}>{(report) => <SummaryView report={report} />}</AsyncSection>;
}

function CodeResultTab({ dcId }: { dcId: string }) {
  const state = useApiResource(() => api.getCodeResultReport(dcId, PROGRAM_NAME), [dcId]);
  return <AsyncSection state={state}>{(report) => <CodeResultTable rows={report.rows} />}</AsyncSection>;
}

function ReportTabBody({ dcId, tab }: { dcId: string; tab: ReportTab }) {
  switch (tab) {
    case "Consolidated":
      return <ConsolidatedTab dcId={dcId} />;
    case "Detailed":
      return <DetailedTab dcId={dcId} />;
    case "Summary":
      return <SummaryTab />;
    case "Code-Result":
      return <CodeResultTab dcId={dcId} />;
  }
}

export function Reports() {
  const [activeTab, setActiveTab] = useState<ReportTab>("Consolidated");
  const [selectedTestRunId, setSelectedTestRunId] = useState<string | null>(null);

  const testRunsState = useApiResource(() => api.listTestRuns(MODEL_ID), [MODEL_ID]);

  useEffect(() => {
    if (testRunsState.status === "ready" && selectedTestRunId === null && testRunsState.data.length > 0) {
      setSelectedTestRunId(testRunsState.data[0].test_run_id);
    }
  }, [testRunsState, selectedTestRunId]);

  const testRunDetailState = useApiResource(
    () => (selectedTestRunId ? api.getTestRun(selectedTestRunId) : Promise.reject(new Error("no test run selected"))),
    [selectedTestRunId],
  );

  return (
    <div>
      <DemoDataNote>
        model <code>{MODEL_ID}</code> &mdash;{" "}
        {testRunsState.status === "ready" ? testRunsState.data.length : "…"} seeded demo test runs (healthy /
        crash-noise / slippage scenarios).
      </DemoDataNote>

      <Panel className="mb-6">
        <SectionTitle>Test run</SectionTitle>
        <AsyncSection state={testRunsState}>
          {(runs) => (
            <select
              className="w-full rounded border border-graticule bg-dark-background px-2 py-1 font-mono text-sm text-white"
              value={selectedTestRunId ?? ""}
              onChange={(event) => setSelectedTestRunId(event.target.value)}
            >
              {runs.map((run) => (
                <option key={run.test_run_id} value={run.test_run_id}>
                  {run.serial_number} &mdash; {run.overall_result}
                </option>
              ))}
            </select>
          )}
        </AsyncSection>
      </Panel>

      <div className="mb-6 flex gap-1">
        {REPORT_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={[
              "rounded-t px-4 py-2 font-display text-sm tracking-wide transition-colors",
              activeTab === tab
                ? "bg-dark-panel text-dark-accentPrimary"
                : "text-dark-secondaryText hover:text-dark-accentSecondary",
            ].join(" ")}
          >
            {tab}
          </button>
        ))}
      </div>

      <Panel>
        <SectionTitle>{activeTab} report</SectionTitle>
        <AsyncSection state={testRunDetailState}>
          {(detail) =>
            detail.dc_records.length === 0 ? (
              <p className="font-mono text-xs text-dark-secondaryText">This test run has no DC records.</p>
            ) : (
              <ReportTabBody dcId={detail.dc_records[0].dc_id} tab={activeTab} />
            )
          }
        </AsyncSection>
      </Panel>
    </div>
  );
}
