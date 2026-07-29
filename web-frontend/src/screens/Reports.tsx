import { useState } from "react";
import { GearGlyph } from "../components/GearGlyph";
import { TodoBanner } from "../components/TodoBanner";

const REPORT_TABS = ["Consolidated", "Detailed", "Summary"] as const;
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

export function Reports() {
  const [activeTab, setActiveTab] = useState<ReportTab>("Consolidated");

  return (
    <div>
      <TodoBanner>
        wire to <code>analysis_engine.reports</code> /{" "}
        <code>nvh_api_schemas.report</code> once Phase D (flat CODE-RESULT
        grading table) and Phase E (report/column configuration) land.
      </TodoBanner>

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

      <div className="rounded border border-graticule bg-dark-panel p-6">
        <h2 className="mb-4 font-display text-base text-white">{activeTab} report</h2>
        <div className="mb-6 flex gap-8">
          <StampPreview result="PASS" />
          <StampPreview result="FAIL" />
        </div>
        <p className="font-mono text-xs text-dark-secondaryText">
          {activeTab} report layout placeholder &mdash; no report data wired up yet.
        </p>
      </div>
    </div>
  );
}
