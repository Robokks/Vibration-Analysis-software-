import { TodoBanner } from "../components/TodoBanner";

const DIRECTION_CYCLE = ["RU", "STYD", "STYC", "RD"] as const;
const GEAR_LABELS = ["N", "R", "I", "II", "III", "IV", "V"] as const;

const PARAMETER_FAMILIES = [
  { name: "Base", count: 14, pattern: "{Mean,Variance,Skewness,Kurtosis,RMS,PK,Crest} x {max,avg}" },
  { name: "Unit-family", count: 8, pattern: "{RMS,PK} x {max,avg} x {(m/s2),(dB m/s2)}" },
  { name: "Harmonic", count: 27, pattern: "{IN_H1-3,CM_H1-3,IN_S1.0,OUT_S1.0,OUTPUT_S1.0} x {(g),(m/s2),(dB m/s2)}" },
];

export function MasterEntry() {
  return (
    <div>
      <TodoBanner>
        wire to the model/master-signature API once Phase C (named
        <code> NVH-PROGRAM</code> profiles + LIMIT/THRESHOLD config) lands &mdash;
        this screen only lays out the shape today.
      </TodoBanner>

      <section className="mb-6 rounded border border-graticule bg-dark-panel p-4">
        <h2 className="mb-3 font-display text-sm uppercase tracking-wide text-dark-accentPrimary">
          Model &amp; gear
        </h2>
        <div className="flex flex-wrap gap-2">
          {GEAR_LABELS.map((label) => (
            <span
              key={label}
              className="rounded border border-graticule px-2 py-1 font-mono text-xs text-dark-secondaryText"
            >
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="mb-6 rounded border border-graticule bg-dark-panel p-4">
        <h2 className="mb-3 font-display text-sm uppercase tracking-wide text-dark-accentPrimary">
          Direction cycle
        </h2>
        <div className="flex items-center gap-2 font-mono text-sm">
          {DIRECTION_CYCLE.map((direction, index) => (
            <span key={direction} className="flex items-center gap-2">
              <span className="rounded bg-dark-background px-2 py-1 text-dark-accentSecondary">
                {direction}
              </span>
              {index < DIRECTION_CYCLE.length - 1 && (
                <span className="text-dark-secondaryText">&rarr;</span>
              )}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded border border-graticule bg-dark-panel p-4">
        <h2 className="mb-3 font-display text-sm uppercase tracking-wide text-dark-accentPrimary">
          Parameter catalog (49 graded parameters)
        </h2>
        <table className="w-full border-collapse font-mono text-xs">
          <thead>
            <tr className="text-left text-dark-secondaryText">
              <th className="border-b border-graticule pb-2 pr-4">Family</th>
              <th className="border-b border-graticule pb-2 pr-4">Count</th>
              <th className="border-b border-graticule pb-2">Pattern</th>
            </tr>
          </thead>
          <tbody>
            {PARAMETER_FAMILIES.map((family) => (
              <tr key={family.name}>
                <td className="border-b border-graticule/40 py-2 pr-4 text-white">
                  {family.name}
                </td>
                <td className="border-b border-graticule/40 py-2 pr-4">{family.count}</td>
                <td className="border-b border-graticule/40 py-2 text-dark-secondaryText">
                  {family.pattern}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
