import type { ReactNode } from "react";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded border border-graticule bg-dark-panel p-4 ${className}`}>
      {children}
    </section>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 font-display text-sm uppercase tracking-wide text-dark-accentPrimary">
      {children}
    </h2>
  );
}
