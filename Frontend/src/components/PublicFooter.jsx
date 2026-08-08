import { Link } from "react-router-dom";
import "./PublicChrome.css";

export default function PublicFooter() {
  return (
    <footer className="public-footer">
      <div className="public-footer-inner">
        <div>
          <Link className="public-brand footer-brand" to="/">
            <span className="public-brand-mark" aria-hidden="true">A</span>
            <span><strong>AskMyCity</strong><small>Find better local choices.</small></span>
          </Link>
          <p>Search local businesses by what actually matters: location, amenities, dietary needs, services, and verified business information.</p>
        </div>
        <div className="public-footer-links">
          <div><strong>Discover</strong><Link to="/">Search</Link><Link to="/explore">Explore businesses</Link></div>
          <div><strong>Your account</strong><Link to="/favorites">Saved places</Link><Link to="/login">Sign in</Link></div>
          <div><strong>Business</strong><Link to="/register">List your business</Link><Link to="/dashboard">Business Studio</Link></div>
        </div>
      </div>
      <div className="public-footer-bottom"><span>© 2026 AskMyCity</span><span>Business details can change. Confirm important information before visiting.</span></div>
    </footer>
  );
}
