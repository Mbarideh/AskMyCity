import { Link, useLocation } from "react-router-dom";
import DashboardShell from "./DashboardShell";
import "./dashboard.css";

const pages = {
  "/dashboard/gallery": ["Gallery Studio", "Build a visual story for your business", "Logo, cover photo, food, interior, and team collections will be managed here."],
  "/dashboard/reviews": ["Reviews Center", "Understand what customers are saying", "Review summaries, replies, and reputation insights are coming in the next sprint."],
  "/dashboard/insights": ["Insights", "Turn customer activity into clear decisions", "Views, calls, directions, menu engagement, and search trends will appear here."],
  "/dashboard/coach": ["AI Coach", "Actionable guidance for your business", "Your full Business Health report and prioritized growth recommendations will live here."],
  "/dashboard/settings": ["Settings", "Manage your Business Studio preferences", "Account, notifications, appearance, and team access will be managed here."],
};

export default function StudioPlaceholderPage() {
  const location = useLocation();
  const [title, subtitle, text] = pages[location.pathname] || pages["/dashboard/insights"];
  return <DashboardShell><section className="studio-page-heading"><div><p className="studio-kicker">BUSINESS STUDIO</p><h1>{title}</h1><p>{subtitle}</p></div></section><section className="studio-card placeholder-card"><span>✦</span><h2>This studio is ready for the next sprint</h2><p>{text}</p><Link className="studio-button primary" to="/dashboard">Back to Home</Link></section></DashboardShell>;
}
