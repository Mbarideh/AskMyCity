import { useEffect, useState } from "react";
import DashboardShell from "./DashboardShell";
import { useAuth } from "../../context/AuthContext";
import { getBusinessReviews, replyToBusinessReview } from "../../services/api";
import "./dashboard.css";

export default function ReviewsPage() {
  const { token } = useAuth();
  const [reviews, setReviews] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadReviews() {
    try {
      setError("");
      const rows = await getBusinessReviews(token);
      setReviews(rows);
      setDrafts(Object.fromEntries(rows.map((review) => [review.id, review.owner_reply || ""])));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  useEffect(() => { loadReviews(); }, [token]);

  async function saveReply(reviewId) {
    try {
      setSavingId(reviewId);
      setError("");
      setMessage("");
      const updated = await replyToBusinessReview(token, reviewId, drafts[reviewId] || "");
      setReviews((current) => current.map((review) => review.id === reviewId ? updated : review));
      setMessage("Your public reply was saved.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  return (
    <DashboardShell>
      <div className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">REVIEWS</p>
          <h1>Customer reviews</h1>
          <p>Read real customer feedback and publish a reply on your business page.</p>
        </div>
      </div>
      {error && <div className="dashboard-alert error">{error}</div>}
      {message && <div className="dashboard-alert">{message}</div>}
      <section className="dashboard-panel">
        {reviews.length === 0 ? (
          <p>No customer reviews yet.</p>
        ) : reviews.map((review) => (
          <article className="review-management-card" key={review.id}>
            <div className="activity-row">
              <span>★</span>
              <div>
                <strong>{review.user_name} · {review.rating}/5</strong>
                <p>{review.comment || "No written comment."}</p>
              </div>
              <small>{new Date(review.created_at).toLocaleDateString()}</small>
            </div>
            <label className="review-reply-label" htmlFor={`reply-${review.id}`}>Public owner reply</label>
            <textarea
              id={`reply-${review.id}`}
              value={drafts[review.id] || ""}
              onChange={(event) => setDrafts((current) => ({ ...current, [review.id]: event.target.value }))}
              placeholder="Thank the customer or respond professionally..."
              maxLength={3000}
              rows={4}
            />
            <button type="button" className="studio-button primary" disabled={savingId === review.id} onClick={() => saveReply(review.id)}>
              {savingId === review.id ? "Saving..." : "Save reply"}
            </button>
          </article>
        ))}
      </section>
    </DashboardShell>
  );
}
