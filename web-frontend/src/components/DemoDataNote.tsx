import type { ReactNode } from "react";

/** Flags a screen as wired to the real API but backed by a single fixed
 * demo dataset (one model/program/gear/direction) -- not a placeholder.
 * Deliberately distinct from TodoBanner (cyan accentSecondary, not amber
 * accentPrimary) since this screen is wired now, just narrow in scope. */
export function DemoDataNote({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 rounded border border-dark-accentSecondary/40 bg-dark-panel px-4 py-2 font-mono text-xs text-dark-accentSecondary">
      DEMO DATA: {children}
    </div>
  );
}
