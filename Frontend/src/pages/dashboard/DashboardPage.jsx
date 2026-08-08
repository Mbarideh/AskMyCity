import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getBusinessStudioOverview } from "../../services/api";
import DashboardShell from "./DashboardShell";
import "./dashboard.css";

const metricIcons = {
  "Profile views": "◎",
  "Menu views": "▤",
  "Direction requests": "⌖",
  "Phone clicks": "☎",
  "Website clicks": "↗",
  Favorites: "♥",
  Reviews: "★",
};

const keyMetricLabels = ["Profile views", "Direction requests", "Phone clicks", "Favorites"];

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const businessUser = ["business_owner", "independent_worker"].includes(user.account_type);

  const loadOverview = useCallback(() => {
    if (!businessUser) return;
    setError("");
    getBusinessStudioOverview(token).then(setData).catch((requestError) => setError(requestError.message));
  }, [token, businessUser]);

  useEffect(() => {
    loadOverview();
    const onVisible = () => {
      if (document.visibilityState === "visible") loadOverview();
    };
    window.addEventListener("focus", loadOverview);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(loadOverview, 30000);
    return () => {
      window.removeEventListener("focus", loadOverview);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [loadOverview]);

  return (
    <DashboardShell>
      {!businessUser ? <CustomerDashboard /> : <BusinessWorkspace data={data} error={error} user={user} />}
    </DashboardShell>
  );
}

function BusinessWorkspace({ data, error, user }) {
  if (error) return <div className="studio-alert error">{error}</div>;
  if (!data) return <DashboardSkeleton />;

  const firstName = user.name.split(" ")[0];
  const greeting = greetingForHour(new Date().getHours());
  const metricsByLabel = Object.fromEntries(data.metrics.map((metric) => [metric.label, metric]));
  const profileViews = metricsByLabel["Profile views"];
  const keyMetrics = keyMetricLabels.map((label) => metricsByLabel[label]).filter(Boolean);
  const secondaryMetrics = data.metrics.filter((metric) => !keyMetricLabels.includes(metric.label));
  const readinessAction = recommendationPath(data.coach?.action_path);

  return (
    <>
      <section className="studio-page-heading studio-page-heading-polished">
        <div>
          <p className="studio-kicker">BUSINESS OVERVIEW</p>
          <h1>{greeting}, {firstName}</h1>
          <div className="business-identity-line">
            <strong>{data.business_name}</strong>
            {data.review_count > 0 && (
              <span className="identity-rating">★ {Number(data.average_rating || 0).toFixed(1)} <i>({data.review_count})</i></span>
            )}
            <span className={data.is_published ? "identity-badge published" : "identity-badge"}>
              {data.is_published ? "Published" : "Draft"}
            </span>
          </div>
          <p className="hero-performance-copy">
            {profileViews?.value > 0
              ? <>Your public page had <strong>{profileViews.value.toLocaleString()} view{profileViews.value === 1 ? "" : "s"}</strong> in the last 7 days.</>
              : <>Your activity will appear here as customers discover and use your public page.</>}
          </p>
        </div>
        <div className="studio-heading-actions">
          <Link className="studio-button secondary" to={data.place_id ? `/places/${data.place_id}` : "/"}>View public page</Link>
          <Link className="studio-button primary" to="/dashboard/profile">Edit business</Link>
        </div>
      </section>

      {!data.is_published && (
        <section className="studio-publish-banner">
          <div>
            <span aria-hidden="true">●</span>
            <div>
              <strong>Your business page is still a draft</strong>
              <p>Finish the profile, confirm the location and publish when you are ready to be discovered.</p>
            </div>
          </div>
          <Link to="/dashboard/profile">Finish setup →</Link>
        </section>
      )}

      <section className="studio-metric-grid studio-metric-grid-primary" aria-label="Customer activity">
        {keyMetrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      <section className="studio-overview-grid">
        <article className="studio-card readiness-card">
          <div className="card-heading">
            <div>
              <p>PAGE READINESS</p>
              <h2>{data.health_status}</h2>
            </div>
            <span className="readiness-score">{data.health_score}/100</span>
          </div>

          <div className="readiness-progress" aria-label={`Page readiness ${data.health_score} out of 100`}>
            <span style={{ width: `${data.health_score}%` }} />
          </div>

          <div className="readiness-list">
            {data.health_dimensions.map((item) => (
              <div className="readiness-row" key={item.label}>
                <div>
                  <strong>{item.label}</strong>
                  <small>{healthHint(item.label, item.score)}</small>
                </div>
                <span>{item.score}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="studio-card next-step-card">
          <p className="studio-card-eyebrow">RECOMMENDED NEXT STEP</p>
          <h2>{data.coach?.title || "Keep your business information current"}</h2>
          <p>{data.coach?.message || "Accurate hours, services, photos and menu details help customers decide faster."}</p>
          {data.coach?.impact && (
            <div className="next-step-impact">
              <span aria-hidden="true">↗</span>
              <div><small>WHY IT MATTERS</small><strong>{data.coach.impact}</strong></div>
            </div>
          )}
          <Link className="studio-button primary" to={readinessAction}>
            {safeActionLabel(data.coach?.action_label)} →
          </Link>
        </article>
      </section>

      {secondaryMetrics.length > 0 && (
        <section className="studio-secondary-metrics">
          <div className="section-title"><div><p>MORE ACTIVITY</p><h2>Other customer actions</h2></div></div>
          <div className="secondary-metric-row">
            {secondaryMetrics.map((metric) => (
              <div key={metric.label}>
                <span aria-hidden="true">{metricIcons[metric.label] || "•"}</span>
                <strong>{metric.value.toLocaleString()}</strong>
                <small>{metric.label}</small>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="studio-lower-grid">
        <article className="studio-card activity-card">
          <div className="card-heading">
            <div><p>RECENT ACTIVITY</p><h2>What customers are doing</h2></div>
          </div>
          <div className="activity-list">
            {data.activity.map((item, index) => (
              <div className={`activity-row activity-${item.type || "profile"}`} key={`${item.title}-${index}`}>
                <span aria-hidden="true">{activityIcon(item.type)}</span>
                <div><strong>{item.title}</strong><p>{item.detail}</p></div>
                <small>{relativeTime(item.occurred_at)}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="studio-card quick-card">
          <div className="card-heading"><div><p>QUICK ACTIONS</p><h2>Keep your listing useful</h2></div></div>
          <div className="quick-grid">
            <Link to="/dashboard/profile"><span>▣</span><strong>Update business info</strong><small>Hours, location, services and photos</small><b>→</b></Link>
            <Link to="/dashboard/menu"><span>≡</span><strong>Manage menu</strong><small>Keep items, prices and availability current</small><b>→</b></Link>
            <Link to="/dashboard/reviews"><span>★</span><strong>Read reviews</strong><small>Reply to AskMyCity customer feedback</small><b>→</b></Link>
            <Link to={data.place_id ? `/places/${data.place_id}` : "/"}><span>↗</span><strong>View public page</strong><small>See exactly what customers see</small><b>→</b></Link>
          </div>
        </article>
      </section>
    </>
  );
}

function MetricCard({ metric }) {
  return (
    <article className={`studio-metric-card ${metric.value === 0 ? "metric-empty" : ""}`}>
      <div>
        <span aria-hidden="true">{metricIcons[metric.label] || "•"}</span>
        <b className={metric.change_percent > 0 ? "positive" : metric.change_percent < 0 ? "negative" : "neutral"}>
          {metric.change_percent > 0 ? `+${metric.change_percent}%` : metric.change_percent < 0 ? `${metric.change_percent}%` : "—"}
        </b>
      </div>
      <strong>{metric.value.toLocaleString()}</strong>
      <p>{metric.label}</p>
      <small>Last 7 days</small>
    </article>
  );
}

function greetingForHour(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function activityIcon(type) {
  const icons = {
    menu: "≡",
    review: "★",
    favorite: "♥",
    phone: "☎",
    direction: "⌖",
    website: "↗",
    profile: "◎",
    tip: "•",
  };
  return icons[type] || "◎";
}

function healthHint(label, score) {
  if (score >= 85) return "This part is in good shape.";
  const hints = {
    Visibility: "Add accurate categories and service details.",
    Trust: "Keep contact details and customer information complete.",
    Completeness: "Finish the missing business profile sections.",
    Freshness: "Keep hours, photos and business details current.",
    Engagement: "Add menu details and respond to customer reviews.",
  };
  return hints[label] || "A few updates can improve this section.";
}

function recommendationPath(path) {
  const safePaths = ["/dashboard/profile", "/dashboard/menu", "/dashboard/reviews"];
  if (safePaths.includes(path)) return path;
  if (typeof path === "string" && path.startsWith("/places/")) return path;
  return "/dashboard/profile";
}

function safeActionLabel(label) {
  if (!label) return "Update business";
  const normalized = label.toLowerCase();
  if (normalized.includes("coach") || normalized.includes("history")) return "Update business";
  return label;
}

function relativeTime(value) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "Recently";
  const hours = Math.max(0, Math.floor((Date.now() - timestamp) / 3600000));
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function DashboardSkeleton() {
  return (
    <>
      <div className="skeleton heading-skeleton" />
      <div className="studio-metric-grid">{[1, 2, 3, 4].map((item) => <div className="skeleton metric-skeleton" key={item} />)}</div>
      <div className="studio-overview-grid"><div className="skeleton big-skeleton" /><div className="skeleton big-skeleton" /></div>
    </>
  );
}

function CustomerDashboard() {
  return (
    <section className="studio-card customer-empty">
      <span aria-hidden="true">⌖</span>
      <h1>Your local places, in one account</h1>
      <p>Discover businesses, save useful places and share reviews with your community.</p>
      <div className="customer-dashboard-actions">
        <Link className="studio-button primary" to="/">Discover places</Link>
        <Link className="studio-button secondary" to="/favorites">View saved places</Link>
      </div>
    </section>
  );
}
