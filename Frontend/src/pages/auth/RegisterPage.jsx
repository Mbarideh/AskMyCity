import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { loginUser, registerUser } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import "./auth.css";

const ROLES = [
  ["customer", "Local explorer", "Find and save businesses around you."],
  ["business_owner", "Business owner", "Create and manage a public business page."],
  ["independent_worker", "Independent professional", "List your local service and availability."],
];

export default function RegisterPage() {
  const [form, setForm] = useState({ name: "", email: "", password: "", account_type: "customer", business_name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  async function submit(event) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      await registerUser({ ...form, business_name: form.business_name || null });
      const session = await loginUser({ email: form.email, password: form.password });
      login(session);
      navigate("/dashboard");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-layout auth-layout-register">
        <aside className="auth-story">
          <Link className="auth-story-brand" to="/"><span>A</span><strong>AskMyCity</strong></Link>
          <div className="auth-story-copy">
            <p>ONE LOCAL ACCOUNT</p>
            <h1>Discover your city or put your business on the map.</h1>
            <span>Customer accounts are free. Business accounts give you a public profile, exact map pin, menu, amenities, reviews and real activity.</span>
          </div>
          <div className="auth-story-note"><strong>Built for local decisions</strong><span>No generic directory profile. AskMyCity keeps useful details structured so people can find the right fit.</span></div>
        </aside>

        <section className="auth-card auth-card-wide">
          <Link className="auth-back" to="/">← Back to Discover</Link>
          <p className="auth-kicker">JOIN ASKMYCITY</p>
          <h2>Create your account</h2>
          <p className="auth-subtitle">Choose how you want to use AskMyCity. You can update your profile later.</p>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>Full name<input value={form.name} onChange={set("name")} autoComplete="name" minLength="2" required /></label>
              <label>Email address<input type="email" value={form.email} onChange={set("email")} autoComplete="email" required /></label>
            </div>
            <label>Password<input type="password" value={form.password} onChange={set("password")} autoComplete="new-password" minLength="8" required /><small className="auth-field-help">Use at least 8 characters.</small></label>
            <fieldset className="role-picker">
              <legend>How will you use AskMyCity?</legend>
              {ROLES.map(([value, title, copy]) => (
                <label key={value} className={form.account_type === value ? "role-option selected" : "role-option"}>
                  <input type="radio" name="role" value={value} checked={form.account_type === value} onChange={set("account_type")} />
                  <span><strong>{title}</strong><small>{copy}</small></span>
                </label>
              ))}
            </fieldset>
            {form.account_type === "business_owner" && <label>Business name<input value={form.business_name} onChange={set("business_name")} required /></label>}
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-auth-button" disabled={loading}>{loading ? "Creating account…" : "Create account"}</button>
          </form>
          <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
        </section>
      </section>
    </main>
  );
}
