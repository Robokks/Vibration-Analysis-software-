import { useCallback, useReducer } from "react";
import { GearGlyph } from "../components/GearGlyph";
import { DemoDataNote } from "../components/DemoDataNote";
import type { LiveEvent } from "../lib/api";
import { useLiveEvents } from "../lib/useLiveEvents";

// 0.8 seconds of trace at the simulator's 5 kHz sample rate -- long enough to
// see the crash-noise burst (~0.3s) and the slippage envelope shift, short
// enough that the SVG polyline stays legible without windowing tricks.
const BUFFER_SIZE = 4000;

// SVG viewBox: x runs 0..BUFFER_SIZE-1 (one unit per sample), y runs -1..1 and
// each frame rescales the trace by max(abs(values)) so the shape fills the box.
const VIEWBOX_WIDTH = BUFFER_SIZE;
const VIEWBOX_HEIGHT = 200;
const Y_PAD = 0.08; // headroom above the peak so the trace doesn't kiss the border

type Stamp = "PENDING" | "PASS" | "FAIL";

interface LiveState {
  station_id: string | null;
  test_run_id: string | null;
  test_run_status: "RUNNING" | "COMPLETED" | null;
  gear_label: string;
  direction: string;
  stamp: Stamp;
  fail_reason_codes: string[];
  buffer: number[];
}

const INITIAL_STATE: LiveState = {
  station_id: null,
  test_run_id: null,
  test_run_status: null,
  gear_label: "—",
  direction: "—",
  stamp: "PENDING",
  fail_reason_codes: [],
  buffer: [],
};

function reduce(state: LiveState, event: LiveEvent): LiveState {
  switch (event.type) {
    case "test_run":
      if (event.status === "RUNNING") {
        // New run starting -- drop the previous trace + stamp so the operator
        // isn't looking at the last unit's data while the next one is running.
        return {
          ...state,
          station_id: event.station_id,
          test_run_id: event.test_run_id,
          test_run_status: "RUNNING",
          stamp: "PENDING",
          fail_reason_codes: [],
          buffer: [],
        };
      }
      return {
        ...state,
        station_id: event.station_id,
        test_run_id: event.test_run_id,
        test_run_status: "COMPLETED",
      };

    case "dc":
      return {
        ...state,
        station_id: event.station_id,
        test_run_id: event.test_run_id,
        gear_label: event.gear_label,
        direction: event.direction,
        stamp: event.stamp,
        fail_reason_codes: event.fail_reason_codes,
      };

    case "signal_chunk": {
      // Concatenating a small array onto a growing buffer + slicing off the
      // tail is O(N) per chunk (500 samples), well within budget at 10 Hz.
      const nextBuffer =
        state.buffer.length + event.values.length <= BUFFER_SIZE
          ? state.buffer.concat(event.values)
          : state.buffer.concat(event.values).slice(-BUFFER_SIZE);
      return {
        ...state,
        station_id: event.station_id,
        test_run_id: event.test_run_id,
        gear_label: event.gear_label,
        direction: event.direction,
        buffer: nextBuffer,
      };
    }
  }
}

function buildPolyline(values: number[]): string {
  if (values.length < 2) return "";
  let peak = 0;
  for (const v of values) {
    const a = Math.abs(v);
    if (a > peak) peak = a;
  }
  const scale = peak > 0 ? peak * (1 + Y_PAD) : 1;
  const midY = VIEWBOX_HEIGHT / 2;
  // Sample indices are laid out starting at 0 so a partially-full buffer
  // draws from the left edge, matching how a scope traces from the trigger.
  const points: string[] = new Array(values.length);
  for (let i = 0; i < values.length; i++) {
    const y = midY - (values[i] / scale) * (VIEWBOX_HEIGHT / 2);
    points[i] = `${i},${y.toFixed(2)}`;
  }
  return points.join(" ");
}

function statusLabel(
  connStatus: "connecting" | "open" | "closed",
  state: LiveState,
): string {
  if (connStatus === "connecting") return "connecting…";
  if (connStatus === "closed") {
    const station = state.station_id ?? "—";
    return `station ${station} — connection lost`;
  }
  const station = state.station_id ?? "—";
  if (state.test_run_status === "RUNNING") {
    const shortId = state.test_run_id ? state.test_run_id.slice(0, 8) : "…";
    return `station ${station} — test ${shortId} running…`;
  }
  if (state.test_run_status === "COMPLETED") {
    const shortId = state.test_run_id ? state.test_run_id.slice(0, 8) : "";
    return `station ${station} — test ${shortId} ${state.stamp === "PENDING" ? "completed" : state.stamp.toLowerCase()}`;
  }
  return `station ${station} — awaiting test run`;
}

function stampClass(stamp: Stamp): string {
  if (stamp === "PASS") return "text-dark-pass";
  if (stamp === "FAIL") return "text-dark-alarm";
  return "text-white";
}

export function LiveDisplay() {
  const [state, dispatch] = useReducer(reduce, INITIAL_STATE);
  // Memoized so useLiveEvents's ref update is a cheap no-op assignment;
  // useReducer's dispatch is stable across renders anyway.
  const onEvent = useCallback((event: LiveEvent) => dispatch(event), []);
  const { status: connStatus } = useLiveEvents(onEvent);

  const polylinePoints = buildPolyline(state.buffer);
  const label = statusLabel(connStatus, state);
  const testRunDisplay = state.test_run_id ?? "—";
  const spinning = connStatus === "open" && state.test_run_status === "RUNNING";

  return (
    <div>
      <DemoDataNote>
        streaming from <code>web-backend/scripts/live_simulator.py</code> via ZeroMQ &rarr; WebSocket &mdash; cycles
        through healthy / crash-noise / slippage units until the LabVIEW producer replaces it.
      </DemoDataNote>

      <div className="mb-4 flex items-center gap-3">
        <GearGlyph spinning={spinning} className="h-8 text-dark-accentSecondary" />
        <span className="font-mono text-sm text-dark-secondaryText">{label}</span>
      </div>

      <div className="graticule-bg mb-6 h-72 rounded border border-graticule">
        <svg
          className="h-full w-full"
          viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
          preserveAspectRatio="none"
          aria-label="Live vibration signal trace"
        >
          {polylinePoints && (
            <polyline
              points={polylinePoints}
              fill="none"
              stroke="currentColor"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
              className="text-dark-accentSecondary"
            />
          )}
        </svg>
      </div>

      <div className="grid grid-cols-2 gap-4 font-mono text-sm sm:grid-cols-4">
        {(
          [
            ["Test run", testRunDisplay, "text-white"],
            ["Gear", state.gear_label, "text-white"],
            ["Direction", state.direction, "text-white"],
            ["Stamp", state.stamp, stampClass(state.stamp)],
          ] as const
        ).map(([labelText, value, colorClass]) => (
          <div key={labelText} className="rounded border border-graticule bg-dark-panel p-3">
            <div className="text-xs uppercase tracking-wide text-dark-secondaryText">{labelText}</div>
            <div className={`mt-1 truncate text-base ${colorClass}`}>{value}</div>
          </div>
        ))}
      </div>

      {state.fail_reason_codes.length > 0 && (
        <div className="mt-3 font-mono text-xs text-dark-alarm">
          fail reasons: {state.fail_reason_codes.join(", ")}
        </div>
      )}
    </div>
  );
}
