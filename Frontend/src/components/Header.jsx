import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="site-header">
      <div>
        <h1>AskMyCity</h1>
        <p>Find trusted local services in your city</p>
      </div>
      <nav className="header-actions">
        {user ? <>
          <Link to="/dashboard">Dashboard</Link>
          <button type="button" onClick={logout}>Sign out</button>
        </> : <>
          <Link to="/login">Sign in</Link>
          <Link className="header-register" to="/register">Create account</Link>
        </>}
      </nav>
    </header>
  );
}
export default Header;
