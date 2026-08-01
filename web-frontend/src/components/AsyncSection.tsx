import type { ReactNode } from "react";
import type { ApiState } from "../lib/useApi";
import { Panel } from "./Panel";

export function AsyncSection<T>({
  state,
  children,
}: {
  state: ApiState<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") {
    return (
      <Panel>
        <p className="font-mono text-xs text-dark-secondaryText">Loading&hellip;</p>
      </Panel>
    );
  }
  if (state.status === "error") {
    return (
      <Panel className="border-dark-alarm/60">
        <p className="font-mono text-xs text-dark-alarm">Failed to load: {state.message}</p>
      </Panel>
    );
  }
  return <>{children(state.data)}</>;
}
