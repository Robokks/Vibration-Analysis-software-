import { NavLink, Outlet } from "react-router-dom";
import { GearGlyph } from "./GearGlyph";

const NAV_ITEMS = [
  { to: "/live", label: "Live Display" },
  { to: "/master-entry", label: "Master Entry" },
  { to: "/reports", label: "Reports" },
];

function navLinkClasses(isActive: boolean) {
  return [
    "rounded px-3 py-1.5 font-display text-sm tracking-wide transition-colors",
    isActive
      ? "bg-dark-panel text-dark-accentPrimary"
      : "text-dark-secondaryText hover:text-dark-accentSecondary",
  ].join(" ");
}

export function AppShell() {
  return (
    <div className="flex h-full min-h-screen flex-col bg-dark-background text-dark-secondaryText">
      <header className="flex items-center justify-between border-b border-graticule bg-dark-panel px-6 py-3">
        <div className="flex items-center gap-3">
          <GearGlyph className="h-6 text-dark-accentPrimary" />
          <div>
            <h1 className="font-display text-lg font-semibold text-white">
              NVH EOL Test System
            </h1>
            <p className="font-mono text-xs text-dark-secondaryText">
              Report GUI &mdash; scaffold build
            </p>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => navLinkClasses(isActive)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
