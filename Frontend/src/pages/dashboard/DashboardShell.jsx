import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const businessLinks = [
  ["/dashboard", "⌂", "Overview", true],
  ["/dashboard/profile", "▣", "Business profile"],
  ["/dashboard/menu", "🍴", "Menu"],
  ["/dashboard/reviews", "★", "Reviews"],
];

export default function DashboardShell({ children }) {
  const { user, logout } = useAuth();
  const business = ["business_owner", "independent_worker"].includes(user.account_type);
  const [theme, setTheme] = useState(() => localStorage.getItem("amc-theme") || "light");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.studioTheme = theme;
    localStorage.setItem("amc-theme", theme);
  }, [theme]);

  const links = business
    ? businessLinks
    : [
        ["/dashboard", "⌂", "Overview", true],
        ["/favorites", "♥", "Saved places"],
      ];

  return (
    <div className="studio-layout">
      <button
        type="button"
        className="studio-mobile-menu"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
      >
        ☰
      </button>

      {mobileOpen && (
        <button
          type="button"
          className="studio-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <aside className={`studio-sidebar ${mobileOpen ? "is-open" : ""}`}>
        <div className="studio-brand-row">
          <NavLink to="/" className="studio-brand" onClick={() => setMobileOpen(false)}>
            <span>A</span>
            <strong>AskMyCity</strong>
          </NavLink>
          <button
            type="button"
            className="studio-sidebar-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>

        <div className="studio-business-switcher">
          <div className="studio-avatar">{user.name.charAt(0).toUpperCase()}</div>
          <span>
            <strong>{user.business_name || user.name}</strong>
            <small>{business ? "Business workspace" : "Local explorer"}</small>
          </span>
        </div>

        <p className="studio-nav-label">{business ? "MANAGE" : "YOUR ACCOUNT"}</p>
        <nav className="studio-nav" aria-label="Dashboard navigation">
          {links.map(([to, icon, label, end]) => (
            <NavLink key={to} end={end} to={to} onClick={() => setMobileOpen(false)}>
              <span className="studio-nav-icon" aria-hidden="true">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="studio-sidebar-footer">
          <NavLink to="/explore" onClick={() => setMobileOpen(false)}>
            <span className="studio-nav-icon" aria-hidden="true">⌖</span>
            Explore AskMyCity
          </NavLink>
          <button type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            <span aria-hidden="true">{theme === "light" ? "☾" : "☀"}</span>
            {theme === "light" ? "Dark mode" : "Light mode"}
          </button>
          <button type="button" onClick={logout}>
            <span aria-hidden="true">↪</span>
            Sign out
          </button>
        </div>
      </aside>

      <main className="studio-main">
        <header className="studio-topbar">
          <div className="studio-topbar-title">
            <span className="studio-status-dot" />
            {business ? "Business workspace" : "Your AskMyCity account"}
          </div>
          <div className="studio-top-actions">
            <NavLink to="/">Discover</NavLink>
            {business && <NavLink to="/dashboard/profile">Edit profile</NavLink>}
            <NavLink className="top-account-button" to={business ? "/dashboard" : "/favorites"} aria-label="Account">
              {user.name.charAt(0).toUpperCase()}
            </NavLink>
          </div>
        </header>
        <div className="studio-content">{children}</div>
      </main>
    </div>
  );
}
