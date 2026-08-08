import { useState } from "react";
import { Link, NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import useFavorites from "../hooks/useFavorites";
import "./PublicChrome.css";

export default function PublicHeader({ compact = false }) {
  const { user, logout } = useAuth();
  const { favorites } = useFavorites();
  const [menuOpen, setMenuOpen] = useState(false);

  const businessUser = ["business_owner", "independent_worker"].includes(user?.account_type);

  return (
    <header className={`public-header ${compact ? "compact" : ""}`}>
      <div className="public-header-inner">
        <Link className="public-brand" to="/" onClick={() => setMenuOpen(false)}>
          <span className="public-brand-mark" aria-hidden="true">A</span>
          <span>
            <strong>AskMyCity</strong>
            <small>Local discovery</small>
          </span>
        </Link>

        <button
          type="button"
          className="public-menu-button"
          aria-label="Toggle navigation"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >
          <span />
          <span />
          <span />
        </button>

        <div className={`public-header-menu ${menuOpen ? "open" : ""}`}>
          <nav className="public-nav" aria-label="Main navigation">
            <NavLink to="/" end onClick={() => setMenuOpen(false)}>Discover</NavLink>
            <NavLink to="/explore" onClick={() => setMenuOpen(false)}>Explore</NavLink>
            <NavLink to={user ? "/favorites" : "/login"} onClick={() => setMenuOpen(false)}>
              Saved{favorites.length ? <span className="public-nav-count">{favorites.length}</span> : null}
            </NavLink>
            <NavLink to={businessUser ? "/dashboard" : "/register"} onClick={() => setMenuOpen(false)}>
              {businessUser ? "Business Studio" : "For business"}
            </NavLink>
          </nav>

          <div className="public-account-actions">
            {user ? (
              <>
                <Link className="public-account-link" to={businessUser ? "/dashboard" : "/favorites"} onClick={() => setMenuOpen(false)}>
                  <span className="public-account-avatar">{(user.name || "U").charAt(0).toUpperCase()}</span>
                  <span className="public-account-copy">
                    <strong>{user.name}</strong>
                    <small>{businessUser ? "Business owner" : "Local explorer"}</small>
                  </span>
                </Link>
                <button type="button" className="public-signout" onClick={() => { logout(); setMenuOpen(false); }}>
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link className="public-signin" to="/login" onClick={() => setMenuOpen(false)}>Sign in</Link>
                <Link className="public-business-cta" to="/register" onClick={() => setMenuOpen(false)}>List your business</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
