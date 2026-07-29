import { GearGlyph } from "../components/GearGlyph";
import { TodoBanner } from "../components/TodoBanner";

const PLACEHOLDER_DC = {
  station_id: "STN-01",
  test_run_id: "—",
  gear_label: "—",
  direction: "—",
  stamp: "PENDING" as const,
};

export function LiveDisplay() {
  return (
    <div>
      <TodoBanner>
        wire to the realtime API once it exists (
        <code>nvh_api_schemas.realtime.LiveDcUpdate</code> over WebSocket) &mdash;
        Phase C&ndash;E land the master-profile/limit config this screen will grade
        against.
      </TodoBanner>

      <div className="mb-4 flex items-center gap-3">
        <GearGlyph spinning className="h-8 text-dark-accentSecondary" />
        <span className="font-mono text-sm text-dark-secondaryText">
          station {PLACEHOLDER_DC.station_id} &mdash; awaiting test run
        </span>
      </div>

      <div className="graticule-bg mb-6 h-72 rounded border border-graticule" />

      <div className="grid grid-cols-2 gap-4 font-mono text-sm sm:grid-cols-4">
        {(
          [
            ["Test run", PLACEHOLDER_DC.test_run_id],
            ["Gear", PLACEHOLDER_DC.gear_label],
            ["Direction", PLACEHOLDER_DC.direction],
            ["Stamp", PLACEHOLDER_DC.stamp],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded border border-graticule bg-dark-panel p-3">
            <div className="text-xs uppercase tracking-wide text-dark-secondaryText">
              {label}
            </div>
            <div className="mt-1 text-base text-white">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
