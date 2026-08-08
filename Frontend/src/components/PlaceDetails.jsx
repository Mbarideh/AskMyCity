import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import BusinessMap from "./BusinessMap";
import PublicFooter from "./PublicFooter";
import PublicHeader from "./PublicHeader";
import { absoluteMediaUrl, getPlace, getPublicMenu, getReviews, recordBusinessEvent, submitReview } from "../services/api";
import { useAuth } from "../context/AuthContext";
import useFavorites from "../hooks/useFavorites";
import { getPlaceFallbackImage, getPlaceImages } from "../utils/placeImages";
import { getMenuCategoryIcon, inferMenuItemIcon } from "../utils/menuIcons";
import "./PlaceDetails.css";

const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const DAY_LABELS = Object.fromEntries(DAY_ORDER.map((day) => [day, day.charAt(0).toUpperCase() + day.slice(1)]));
const MENU_ORDER = ["Food", "Entrées", "Entrees", "Main", "Mains", "Pizza", "Pasta", "Salad", "Dessert", "Drink", "Drinks", "Beverage", "Beverages", "Other"];

function normalizeWebsite(url) {
  if (!url) return "";
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

function parseHours(place) {
  const raw = place?.working_hours_json || place?.working_hours;
  if (!raw) return [];
  let value = raw;
  if (typeof raw === "string") {
    try { value = JSON.parse(raw); }
    catch {
      return raw.split(/\n|\|/).map((line) => line.trim()).filter(Boolean).map((line) => ({ label: line.split(":")[0] || "Hours", value: line.includes(":") ? line.slice(line.indexOf(":") + 1).trim() : line }));
    }
  }
  if (Array.isArray(value)) return value.map((line, index) => ({ label: `Hours ${index + 1}`, value: String(line) }));
  if (!value || typeof value !== "object") return [];

  const keys = [...DAY_ORDER.filter((day) => Object.prototype.hasOwnProperty.call(value, day)), ...Object.keys(value).filter((key) => !DAY_ORDER.includes(key))];
  return keys.map((day) => {
    const entry = value[day];
    if (entry && typeof entry === "object") {
      if (entry.closed === true || entry.is_closed === true) return { label: DAY_LABELS[day] || day, value: "Closed", closed: true };
      const open = entry.open || entry.opens || entry.start || "";
      const close = entry.close || entry.closes || entry.end || "";
      return { label: DAY_LABELS[day] || day, value: open || close ? `${open}${open && close ? " – " : ""}${close}` : "Hours not specified" };
    }
    return { label: DAY_LABELS[day] || day, value: String(entry || "Hours not specified") };
  });
}

const AMENITY_LABELS = {
  services: { dine_in: "Dine-in", takeout: "Takeout", delivery: "Delivery", catering: "Catering", reservations: "Reservations" },
  parking: { free_parking: "Free parking", paid_parking: "Paid parking", street_parking: "Street parking" },
  seating: { indoor_seating: "Indoor seating", patio: "Patio / outdoor seating" },
  accessibility: { wheelchair_entrance: "Wheelchair-accessible entrance", wheelchair_seating: "Wheelchair-accessible seating", wheelchair_washroom: "Wheelchair-accessible washroom" },
  family: { kids_menu: "Kids menu", high_chairs: "High chairs", family_friendly: "Family-friendly" },
  amenities: { wifi: "Wi-Fi", washroom: "Washroom", charging_outlets: "Charging outlets" },
  payments: { credit_card: "Credit card", debit: "Debit", cash: "Cash", contactless: "Contactless payment" },
  dietary: { vegetarian: "Vegetarian options", vegan: "Vegan options", gluten_free: "Gluten-free options" },
};

const AMENITY_GROUP_META = {
  services: ["🍽️", "Service"], parking: ["🅿️", "Parking"], seating: ["🌤️", "Seating"],
  accessibility: ["♿", "Accessibility"], family: ["👨‍👩‍👧", "Family"], amenities: ["📶", "Amenities"],
  dietary: ["🥗", "Dietary"], payments: ["💳", "Payments"],
};

function parseOwnerAmenities(place) {
  const raw = place?.features_json;
  if (!raw) return null;
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    const owner = parsed?.owner_provided?.data || parsed?.owner_provided || null;
    return owner && typeof owner === "object" ? owner : null;
  } catch { return null; }
}

function publicAmenityGroups(place) {
  const data = parseOwnerAmenities(place);
  if (!data) return [];
  const groups = [];
  for (const [key, labels] of Object.entries(AMENITY_LABELS)) {
    const selected = Array.isArray(data[key]) ? data[key] : [];
    const items = selected.map((value) => labels[value]).filter(Boolean);
    if (items.length) {
      const [icon, title] = AMENITY_GROUP_META[key];
      groups.push({ key, icon, title, items });
    }
  }
  const halalLabels = { fully_halal: "Fully halal", halal_options: "Halal options available", not_halal: "Not halal" };
  if (halalLabels[data.halal_status]) {
    const existing = groups.find((group) => group.key === "dietary");
    if (existing) existing.items = [halalLabels[data.halal_status], ...existing.items];
    else groups.push({ key: "dietary", icon: "🥗", title: "Dietary", items: [halalLabels[data.halal_status]] });
  }
  const alcoholLabels = { none: "No alcohol served", beer_wine: "Beer & wine", full_bar: "Full bar / cocktails", serves_alcohol: "Alcohol served" };
  if (alcoholLabels[data.alcohol_status]) groups.push({ key: "alcohol", icon: "🍷", title: "Alcohol", items: [alcoholLabels[data.alcohol_status]] });
  return groups;
}

function groupMenuItems(items) {
  const groups = new Map();
  for (const item of items) {
    const category = String(item.category || "Other").trim() || "Other";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(item);
  }
  return Array.from(groups.entries()).sort(([a], [b]) => {
    const ai = MENU_ORDER.findIndex((key) => key.toLowerCase() === a.toLowerCase());
    const bi = MENU_ORDER.findIndex((key) => key.toLowerCase() === b.toLowerCase());
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

function StarRating({ value }) {
  const numeric = Number(value) || 0;
  return <span className="details-stars" aria-label={`${numeric.toFixed(1)} out of 5 stars`}>{[1,2,3,4,5].map((star) => <span key={star} className={numeric >= star - .25 ? "filled" : ""}>★</span>)}</span>;
}

export default function PlaceDetails() {
  const { placeId } = useParams();
  const navigate = useNavigate();
  const { isFavorite, toggleFavorite } = useFavorites();
  const { token } = useAuth();
  const [place, setPlace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeImage, setActiveImage] = useState(0);
  const [reviews, setReviews] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const menuSectionRef = useRef(null);
  const menuViewTrackedRef = useRef(false);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    async function loadPlace() {
      try {
        setLoading(true); setError("");
        const [data, reviewData, menuData] = await Promise.all([getPlace(placeId), getReviews(placeId), getPublicMenu(placeId)]);
        setPlace(data); setReviews(Array.isArray(reviewData) ? reviewData : []); setMenuItems(Array.isArray(menuData) ? menuData : []);
        recordBusinessEvent(placeId, "profile_view").catch(() => {});
      } catch (requestError) {
        console.error("Could not load business:", requestError);
        setError(requestError.message || "Could not load this business.");
      } finally { setLoading(false); }
    }
    loadPlace();
  }, [placeId]);

  const images = useMemo(() => getPlaceImages(place || {}), [place]);
  const hours = useMemo(() => parseHours(place), [place]);
  const amenityGroups = useMemo(() => publicAmenityGroups(place), [place]);
  const menuGroups = useMemo(() => groupMenuItems(menuItems), [menuItems]);
  const localReviewAverage = useMemo(() => reviews.length ? reviews.reduce((sum, review) => sum + Number(review.rating || 0), 0) / reviews.length : 0, [reviews]);

  useEffect(() => {
    if (!place?.id || !menuItems.length || !menuSectionRef.current || menuViewTrackedRef.current) return undefined;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.25) && !menuViewTrackedRef.current) {
        menuViewTrackedRef.current = true;
        recordBusinessEvent(place.id, "menu_view").catch(() => {});
        observer.disconnect();
      }
    }, { threshold: [0.25] });
    observer.observe(menuSectionRef.current);
    return () => observer.disconnect();
  }, [menuItems.length, place?.id]);

  if (loading) return <div className="details-page-shell"><PublicHeader /><main className="details-page"><div className="details-container"><div className="details-status-card"><div className="details-spinner" /><h2>Loading business</h2><p>Getting the latest details.</p></div></div></main></div>;
  if (error || !place) return <div className="details-page-shell"><PublicHeader /><main className="details-page"><div className="details-container"><div className="details-status-card error"><h2>Business not found</h2><p>{error || "This business could not be found."}</p><button type="button" onClick={() => navigate("/")}>Back to Discover</button></div></div></main></div>;

  const rating = Number(place.rating) || 0;
  const reviewCount = Number(place.review_count) || 0;
  const address = place.full_address || place.address || [place.city, place.state, place.postal_code].filter(Boolean).join(", ");
  const website = normalizeWebsite(place.website);
  const saved = isFavorite(place.id);
  const hasMap = Number.isFinite(Number(place.latitude)) && Number.isFinite(Number(place.longitude));

  async function handleReviewSubmit(event) {
    event.preventDefault();
    if (!token) { navigate("/login"); return; }
    try {
      setReviewMessage("");
      await submitReview(token, place.id, { rating: Number(reviewRating), comment: reviewComment.trim() || null });
      const updatedReviews = await getReviews(place.id);
      setReviews(Array.isArray(updatedReviews) ? updatedReviews : []);
      setReviewComment("");
      setReviewMessage("Your review was saved.");
    } catch (reviewError) { setReviewMessage(reviewError.message); }
  }

  function track(eventType) { recordBusinessEvent(place.id, eventType).catch(() => {}); }
  function handleSave() {
    if (!token) {
      navigate("/login", { state: { from: `/places/${place.id}` } });
      return;
    }
    toggleFavorite(place);
  }
  function handleImageError(event) { event.currentTarget.onerror = null; event.currentTarget.src = getPlaceFallbackImage(place); }

  return (
    <div className="details-page-shell">
      <PublicHeader />
      <main className="details-page">
        <div className="details-container">
          <div className="details-toolbar">
            <button type="button" className="details-back" onClick={() => navigate(-1)}>← Back</button>
            <button type="button" className={`details-save ${saved ? "saved" : ""}`} onClick={handleSave} aria-pressed={saved}>{saved ? "♥ Saved" : "♡ Save"}</button>
          </div>

          <section className="details-photo-grid" aria-label={`${place.name} photos`}>
            <button type="button" className="details-main-photo" onClick={() => setActiveImage(0)} aria-label="View main business photo"><img src={images[activeImage] || getPlaceFallbackImage(place)} alt={`${place.name} business`} onError={handleImageError} /></button>
            <div className="details-photo-side">
              {images.slice(1, 3).map((image, index) => <button type="button" key={`${image}-${index}`} onClick={() => setActiveImage(index + 1)}><img src={image} alt={`${place.name} photo ${index + 2}`} onError={handleImageError} /></button>)}
              {images.length <= 1 && <div className="details-photo-placeholder"><span>⌖</span><p>Local business</p></div>}
            </div>
          </section>

          <section className="details-business-summary">
            <div className="details-summary-main">
              <div className="details-title-badges"><span>{place.category || "Local business"}</span>{place.verified && <b>✓ Verified</b>}</div>
              <h1>{place.name}</h1>
              <div className="details-rating-line">{rating > 0 ? <><strong>{rating.toFixed(1)}</strong><StarRating value={rating} />{reviewCount > 0 && <span>{reviewCount.toLocaleString()} public reviews</span>}</> : <span>No public rating yet</span>}</div>
              {address && <p className="details-address"><span>⌖</span>{address}</p>}
            </div>
            <div className="details-summary-actions">
              {place.phone_number && <a className="details-action primary" href={`tel:${place.phone_number}`} onClick={() => track("phone_click")}>Call</a>}
              {place.google_maps_url && <a className="details-action" href={place.google_maps_url} target="_blank" rel="noreferrer" onClick={() => track("direction_click")}>Directions</a>}
              {website && <a className="details-action" href={website} target="_blank" rel="noreferrer" onClick={() => track("website_click")}>Website</a>}
            </div>
          </section>

          <section className="details-layout">
            <div className="details-main-column">
              <article className="details-section"><p className="details-section-kicker">ABOUT</p><h2>About {place.name}</h2><p className="details-body-copy">{place.description || `${place.name} is a local ${place.category || "business"} serving ${place.city || "the surrounding community"}.`}</p></article>

              {amenityGroups.length > 0 && <article className="details-section"><div className="details-section-heading"><div><p className="details-section-kicker">AMENITIES & SERVICES</p><h2>What you can expect</h2></div><span className="details-owner-source">Provided by business</span></div><div className="public-amenities-grid">{amenityGroups.map((group) => <div className="public-amenity-group" key={group.key}><span className="public-amenity-icon">{group.icon}</span><div><strong>{group.title}</strong><div className="public-amenity-chips">{group.items.map((item) => <span key={item}>{item}</span>)}</div></div></div>)}</div></article>}

              {menuGroups.length > 0 && <article className="details-section" ref={menuSectionRef}><p className="details-section-kicker">MENU</p><h2>Menu</h2><p className="details-section-note">Available items published by the business.</p><div className="public-menu-groups">{menuGroups.map(([category, items]) => <section key={category} className="public-menu-group"><div className="public-menu-group-heading"><h3><span className="public-menu-category-icon" aria-hidden="true">{getMenuCategoryIcon(category)}</span>{category}</h3><span>{items.length} item{items.length === 1 ? "" : "s"}</span></div><div className="public-menu-grid">{items.map((item) => <article className="public-menu-item" key={item.id}>{item.photo_url ? <img src={absoluteMediaUrl(item.photo_url)} alt={item.name} loading="lazy" /> : <div className="public-menu-item-placeholder" aria-hidden="true"><span>{inferMenuItemIcon(item)}</span></div>}<div><div className="public-menu-item-title"><strong>{item.name}</strong>{item.price !== null && item.price !== undefined && <b>${Number(item.price).toFixed(2)}</b>}</div>{item.description && <p>{item.description}</p>}{item.is_featured && <span className="public-menu-featured">★ Popular</span>}</div></article>)}</div></section>)}</div></article>}

              {hours.length > 0 && <article className="details-section"><p className="details-section-kicker">HOURS</p><h2>Business hours</h2><div className="details-hours-grid">{hours.map((item, index) => <div key={`${item.label}-${index}`} className={item.closed ? "closed" : ""}><strong>{item.label}</strong><span>{item.value}</span></div>)}</div></article>}

              <article className="details-section" id="reviews"><p className="details-section-kicker">COMMUNITY REVIEWS</p><h2>AskMyCity reviews</h2><div className="local-review-summary">{reviews.length > 0 ? <><div><strong>{localReviewAverage.toFixed(1)}</strong><StarRating value={localReviewAverage} /><span>{reviews.length} AskMyCity review{reviews.length === 1 ? "" : "s"}</span></div></> : <p>Be the first AskMyCity user to review this business.</p>}</div>
                <form className="details-review-form" onSubmit={handleReviewSubmit}><div className="details-review-form-heading"><h3>Share your experience</h3><label>Rating<select value={reviewRating} onChange={(event) => setReviewRating(event.target.value)}>{[5,4,3,2,1].map((value) => <option key={value} value={value}>{value} star{value === 1 ? "" : "s"}</option>)}</select></label></div><textarea rows="4" value={reviewComment} onChange={(event) => setReviewComment(event.target.value)} placeholder="What should other locals know?" /><button type="submit">Submit review</button>{reviewMessage && <p className="details-form-message">{reviewMessage}</p>}</form>
                {reviews.length > 0 && <div className="details-review-list">{reviews.map((review) => <article key={review.id}><div className="details-review-avatar">{String(review.user_name || "C").charAt(0).toUpperCase()}</div><div><div className="details-review-title"><strong>{review.user_name}</strong><span>{review.rating}/5 ★</span></div><p>{review.comment || "No written comment."}</p>{review.owner_reply && <div className="details-owner-reply"><strong>Business reply</strong><p>{review.owner_reply}</p></div>}</div></article>)}</div>}
              </article>
            </div>

            <aside className="details-side-column">
              <div className="details-contact-card"><h2>Business details</h2><div className="details-info-list">{address && <div><span>⌖</span><p><strong>Address</strong>{address}</p></div>}{place.phone_number && <div><span>☎</span><p><strong>Phone</strong><a href={`tel:${place.phone_number}`} onClick={() => track("phone_click")}>{place.phone_number}</a></p></div>}{website && <div><span>↗</span><p><strong>Website</strong><a href={website} target="_blank" rel="noreferrer" onClick={() => track("website_click")}>Visit website</a></p></div>}</div>{place.phone_number && <a className="details-side-button primary" href={`tel:${place.phone_number}`} onClick={() => track("phone_click")}>Call now</a>}{place.google_maps_url && <a className="details-side-button" href={place.google_maps_url} target="_blank" rel="noreferrer" onClick={() => track("direction_click")}>Get directions</a>}<button type="button" className={`details-side-button ${saved ? "saved" : ""}`} onClick={handleSave}>{saved ? "♥ Saved" : "♡ Save for later"}</button></div>
              {hasMap && <div className="details-map-card"><div className="details-map-heading"><strong>Location</strong><span>Exact business pin</span></div><BusinessMap businesses={[place]} onBusinessSelect={() => {}} /></div>}
            </aside>
          </section>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
