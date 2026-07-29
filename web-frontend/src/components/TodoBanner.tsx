import type { ReactNode } from "react";

type TodoBannerProps = {
  children: ReactNode;
};

/** Flags a screen as scaffold-only: layout and visual language are real, data is not. */
export function TodoBanner({ children }: TodoBannerProps) {
  return (
    <div className="mb-6 rounded border border-dark-accentPrimary/40 bg-dark-panel px-4 py-2 font-mono text-xs text-dark-accentPrimary">
      TODO: {children}
    </div>
  );
}
