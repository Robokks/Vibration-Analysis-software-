import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LiveDisplay } from "./screens/LiveDisplay";
import { MasterEntry } from "./screens/MasterEntry";
import { Reports } from "./screens/Reports";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/live" replace />} />
        <Route path="live" element={<LiveDisplay />} />
        <Route path="master-entry" element={<MasterEntry />} />
        <Route path="reports" element={<Reports />} />
      </Route>
    </Routes>
  );
}
