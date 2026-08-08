import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { loginUser } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import "./auth.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  async function submit(event) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const session = await loginUser({ email, password });
      login(session);
      navigate(location.state?.from || "/dashboard");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-layout">
        <aside className="auth-story">
          <Link className="auth-story-brand" to="/"><span>A</span><strong>AskMyCity</strong></Link>
          <div className="auth-story-copy">
            <p>LOCAL DISCOVERY</p>
            <h1>Find places that fit what you actually need.</h1>
            <span>Search by distance, parking, dietary needs, family options and the details that matter in real life.</span>
          </div>
          <div className="auth-story-points">
            <div><b>⌖</b><span><strong>Nearby first</strong><small>Results that respect your location.</small></span></div>
            <div><b>✓</b><span><strong>Useful details</strong><small>Business information you can act on.</small></span></div>
            <div><b>♥</b><span><strong>Save your places</strong><small>Build a personal local shortlist.</small></span></div>
          </div>
        </aside>

        <section className="auth-card">
          <Link className="auth-back" to="/">← Back to Discover</Link>
          <p className="auth-kicker">WELCOME BACK</p>
          <h2>Sign in to AskMyCity</h2>
          <p className="auth-subtitle">Continue discovering local places or manage your business profile.</p>
          <form onSubmit={submit}>
            <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
            <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="8" autoComplete="current-password" required /></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-auth-button" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
          </form>
          <p className="auth-switch">New to AskMyCity? <Link to="/register">Create an account</Link></p>
        </section>
      </section>
    </main>
  );
}
