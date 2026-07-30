import { useEffect, useState } from "react";
import { ApiError, api, type ParameterRow } from "../lib/api";
import { useApiResource } from "../lib/useApi";
import { AsyncSection } from "../components/AsyncSection";
import { DemoDataNote } from "../components/DemoDataNote";
import { Panel, SectionTitle } from "../components/Panel";

// The seeded demo dataset (web-backend/scripts/seed_demo_data.py) has
// exactly one model/program/gear/direction -- hardcoded here rather than
// building selectors, since there's nothing else to select between yet.
// Revisit once a second model/program/gear exists.
const MODEL_ID = "MODEL-A";
const PROGRAM_NAME = "REVA";
const GEAR_LABEL = "R";
const DIRECTION = "RU";
const CHANNEL_NAME = "vib_a";

const DIRECTION_CYCLE = ["RU", "STYD", "STYC", "RD"] as const;

export function MasterEntry() {
  const modelState = useApiResource(() => api.getModel(MODEL_ID), [MODEL_ID]);
  const parametersState = useApiResource(
    () =>
      api.listParameters(MODEL_ID, PROGRAM_NAME, {
        gearLabel: GEAR_LABEL,
        direction: DIRECTION,
        channelName: CHANNEL_NAME,
      }),
    [MODEL_ID, PROGRAM_NAME, GEAR_LABEL, DIRECTION],
  );

  return (
    <div>
      <DemoDataNote>
        model <code>{MODEL_ID}</code>, program <code>{PROGRAM_NAME}</code>, gear{" "}
        <code>{GEAR_LABEL}</code>/<code>{DIRECTION}</code> &mdash; the only combination the seeded
        demo dataset has today.
      </DemoDataNote>

      <Panel className="mb-6">
        <SectionTitle>Model &amp; gear teeth</SectionTitle>
        <AsyncSection state={modelState}>
          {(model) => (
            <table className="w-full border-collapse font-mono text-xs">
              <thead>
                <tr className="text-left text-dark-secondaryText">
                  <th className="border-b border-graticule pb-2 pr-4">Gear</th>
                  <th className="border-b border-graticule pb-2 pr-4">Drive teeth</th>
                  <th className="border-b border-graticule pb-2 pr-4">Idler 1</th>
                  <th className="border-b border-graticule pb-2 pr-4">Layshaft</th>
                  <th className="border-b border-graticule pb-2">Ratio</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(model.ratios).map((label) => (
                  <tr key={label}>
                    <td className="border-b border-graticule/40 py-2 pr-4 text-white">{label}</td>
                    <td className="border-b border-graticule/40 py-2 pr-4">
                      {model.drive_teeth[label] ?? "—"}
                    </td>
                    <td className="border-b border-graticule/40 py-2 pr-4">
                      {model.idler_teeth_1[label] ?? "—"}
                    </td>
                    <td className="border-b border-graticule/40 py-2 pr-4">
                      {model.layshaft_teeth[label] ?? "—"}
                    </td>
                    <td className="border-b border-graticule/40 py-2">{model.ratios[label].toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </AsyncSection>
      </Panel>

      <Panel className="mb-6">
        <SectionTitle>Direction cycle</SectionTitle>
        <div className="flex items-center gap-2 font-mono text-sm">
          {DIRECTION_CYCLE.map((direction, index) => (
            <span key={direction} className="flex items-center gap-2">
              <span
                className={[
                  "rounded px-2 py-1",
                  direction === DIRECTION
                    ? "bg-dark-accentSecondary/20 text-dark-accentSecondary"
                    : "bg-dark-background text-dark-secondaryText",
                ].join(" ")}
              >
                {direction}
              </span>
              {index < DIRECTION_CYCLE.length - 1 && <span className="text-dark-secondaryText">&rarr;</span>}
            </span>
          ))}
        </div>
      </Panel>

      <Panel>
        <SectionTitle>Master &amp; limit parameters</SectionTitle>
        <AsyncSection state={parametersState}>
          {(rows) => <ParameterTable initialRows={rows} />}
        </AsyncSection>
      </Panel>
    </div>
  );
}

// LIMIT and THRESHOLD columns are inline-editable, and the "In table"
// column is a clickable toggle -- mirrors the real system's Limit Config.vi
// (LIMIT override + THRESHOLD margin tuning) plus the Table Config screen's
// per-parameter inclusion checkbox. On every commit we PATCH the backend
// and swap in the returned row so the visual state matches DB state.
function ParameterTable({ initialRows }: { initialRows: ParameterRow[] }) {
  const [rows, setRows] = useState(initialRows);
  useEffect(() => {
    setRows(initialRows);
  }, [initialRows]);

  const applyRow = (updated: ParameterRow) => {
    setRows((current) => current.map((r) => (r.stat_name === updated.stat_name ? updated : r)));
  };

  return (
    <table className="w-full border-collapse font-mono text-xs">
      <thead>
        <tr className="text-left text-dark-secondaryText">
          <th className="border-b border-graticule pb-2 pr-4">Parameter</th>
          <th className="border-b border-graticule pb-2 pr-4">Order</th>
          <th className="border-b border-graticule pb-2 pr-4">Mean</th>
          <th className="border-b border-graticule pb-2 pr-4">Band</th>
          <th className="border-b border-graticule pb-2 pr-4">Full scale</th>
          <th className="border-b border-graticule pb-2 pr-4">Trials</th>
          <th className="border-b border-graticule pb-2 pr-4">Limit lo</th>
          <th className="border-b border-graticule pb-2 pr-4">Limit hi</th>
          <th className="border-b border-graticule pb-2 pr-4">Threshold lo</th>
          <th className="border-b border-graticule pb-2 pr-4">Threshold hi</th>
          <th className="border-b border-graticule pb-2">In table</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <ParameterRowView key={row.stat_name} row={row} onUpdated={applyRow} />
        ))}
      </tbody>
    </table>
  );
}

type LimitField = "limit_low" | "limit_high";
type ThresholdField = "threshold_low" | "threshold_high";
type NumericField = LimitField | ThresholdField;

function ParameterRowView({
  row,
  onUpdated,
}: {
  row: ParameterRow;
  onUpdated: (row: ParameterRow) => void;
}) {
  return (
    <tr>
      <td className="border-b border-graticule/40 py-2 pr-4 text-white">{row.stat_name}</td>
      <td className="border-b border-graticule/40 py-2 pr-4">
        {row.order_number !== null ? row.order_number.toPrecision(4) : "—"}
      </td>
      <td className="border-b border-graticule/40 py-2 pr-4">
        {row.master ? row.master.mean_value.toPrecision(4) : "—"}
      </td>
      <td className="border-b border-graticule/40 py-2 pr-4">
        {row.master
          ? `${row.master.band_min.toPrecision(3)}–${row.master.band_max.toPrecision(3)}`
          : "—"}
      </td>
      <td className="border-b border-graticule/40 py-2 pr-4">
        {row.master ? row.master.full_scale.toPrecision(3) : "—"}
      </td>
      <td className="border-b border-graticule/40 py-2 pr-4">
        {row.master ? row.master.trial_count : "—"}
      </td>
      <NumericCell row={row} field="limit_low" onUpdated={onUpdated} />
      <NumericCell row={row} field="limit_high" onUpdated={onUpdated} />
      <NumericCell row={row} field="threshold_low" onUpdated={onUpdated} />
      <NumericCell row={row} field="threshold_high" onUpdated={onUpdated} />
      <InTableCell row={row} onUpdated={onUpdated} />
    </tr>
  );
}

function NumericCell({
  row,
  field,
  onUpdated,
}: {
  row: ParameterRow;
  field: NumericField;
  onUpdated: (row: ParameterRow) => void;
}) {
  const stored = row[field];
  const editable = stored !== null;
  const [draft, setDraft] = useState(stored !== null ? String(stored) : "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(stored !== null ? String(stored) : "");
    setError(null);
  }, [stored]);

  if (!editable) {
    return <td className="border-b border-graticule/40 py-2 pr-4 text-dark-secondaryText">—</td>;
  }

  const commit = async () => {
    const parsed = Number(draft);
    if (!Number.isFinite(parsed)) {
      setError("not a number");
      setDraft(String(stored));
      return;
    }
    if (parsed === stored) return;
    setError(null);
    setSaving(true);
    try {
      const opts = { gearLabel: GEAR_LABEL, direction: DIRECTION, channelName: CHANNEL_NAME };
      let updated: ParameterRow;
      if (field === "limit_low" || field === "limit_high") {
        updated = await api.patchLimit(MODEL_ID, PROGRAM_NAME, row.stat_name, opts, {
          limit_low: field === "limit_low" ? parsed : (row.limit_low ?? 0),
          limit_high: field === "limit_high" ? parsed : (row.limit_high ?? 0),
        });
      } else {
        updated = await api.patchThreshold(MODEL_ID, PROGRAM_NAME, row.stat_name, opts, {
          threshold_low: field === "threshold_low" ? parsed : (row.threshold_low ?? 0),
          threshold_high: field === "threshold_high" ? parsed : (row.threshold_high ?? 0),
        });
      }
      onUpdated(updated);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "save failed";
      setError(message);
      setDraft(String(stored));
    } finally {
      setSaving(false);
    }
  };

  return (
    <td className="border-b border-graticule/40 py-2 pr-4">
      <input
        type="text"
        inputMode="decimal"
        className={[
          "w-24 rounded border bg-dark-background px-2 py-1 font-mono text-xs text-white",
          "focus:outline-none focus:ring-1 focus:ring-dark-accentSecondary",
          error ? "border-dark-alarm" : "border-graticule",
          saving ? "opacity-60" : "",
        ].join(" ")}
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void commit()}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.currentTarget.blur();
          } else if (e.key === "Escape") {
            setDraft(String(stored));
            setError(null);
            e.currentTarget.blur();
          }
        }}
        title={error ?? undefined}
      />
    </td>
  );
}

function InTableCell({
  row,
  onUpdated,
}: {
  row: ParameterRow;
  onUpdated: (row: ParameterRow) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const included = row.included_in_table_config;

  const toggle = async () => {
    setError(null);
    setSaving(true);
    try {
      const updated = await api.patchTableConfigParameter(
        MODEL_ID,
        PROGRAM_NAME,
        row.stat_name,
        { gearLabel: GEAR_LABEL, direction: DIRECTION, channelName: CHANNEL_NAME },
        { included: !included },
      );
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <td className="border-b border-graticule/40 py-2">
      <button
        type="button"
        onClick={() => void toggle()}
        disabled={saving}
        title={error ?? (included ? "Click to exclude" : "Click to include")}
        className={[
          "rounded px-3 py-1 text-xs font-medium transition-colors",
          included
            ? "bg-dark-pass/20 text-dark-pass hover:bg-dark-pass/30"
            : "bg-dark-background text-dark-secondaryText hover:bg-dark-background/60",
          error ? "ring-1 ring-dark-alarm" : "",
          saving ? "opacity-60" : "",
        ].join(" ")}
      >
        {included ? "yes" : "no"}
      </button>
    </td>
  );
}
