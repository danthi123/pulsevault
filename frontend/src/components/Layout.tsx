import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Home", icon: "🏠", end: true },
  { to: "/heart", label: "Heart", icon: "❤️" },
  { to: "/sleep", label: "Sleep", icon: "🌙" },
  { to: "/steps", label: "Steps", icon: "👣" },
  { to: "/workouts", label: "Workouts", icon: "🏃" },
  { to: "/trends", label: "Trends", icon: "📈" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
];

// A couple of secondary metric pages only shown in the desktop sidebar.
const SIDEBAR_EXTRA = [
  { to: "/stress", label: "Stress", icon: "🌀" },
  { to: "/spo2", label: "SpO₂", icon: "🩸" },
  { to: "/bodybattery", label: "Body Battery", icon: "🔋" },
  { to: "/hrv", label: "HRV", icon: "💓" },
];

export default function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">Pulse<span>Vault</span></div>
        {[...NAV.filter((n) => n.to !== "/settings"), ...SIDEBAR_EXTRA].map((n) => (
          <NavLink key={n.to} to={n.to} end={(n as any).end}
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
            <span className="nav-icon">{n.icon}</span>{n.label}
          </NavLink>
        ))}
        <div style={{ flex: 1 }} />
        <NavLink to="/settings" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
          <span className="nav-icon">⚙️</span>Settings
        </NavLink>
      </aside>

      <main className="main">
        <Outlet />
      </main>

      <nav className="bottom-nav">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={(n as any).end}
            className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="nav-icon">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
