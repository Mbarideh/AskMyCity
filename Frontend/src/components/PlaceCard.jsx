import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import useFavorites from "../hooks/useFavorites";
import { getPlaceFallbackImage, getPrimaryPlaceImage } from "../utils/placeImages";
import "./PlaceCard.css";

const FEATURE_LABELS = {
  dine_in: "Dine-in",
  takeout: "Takeout",
  delivery: "Delivery",
  free_parking: "Free parking",
  street_parking: "Street parking",
  patio: "Patio",
  kids_menu: "Kids menu",
  high_chairs: "High chairs",
  family_friendly: "Family-friendly",
  wifi: "Wi-Fi",
  vegetarian: "Vegetarian",
  vegan: "Vegan",
  gluten_free: "Gluten-free",
};

function getFeaturePreview(place) {
  try {
    const raw = typeof place.features_json === "string" ? JSON.parse(place.features_json) : place.features_json;
    const owner = raw?.owner_provided?.data || raw?.owner_provided || {};
    const values = [];
    for (const group of ["services", "parking", "seating", "family", "amenities", "dietary"]) {
      for (const item of Array.isArray(owner[group]) ? owner[group] : []) {
        if (FEATURE_LABELS[item] && !values.includes(FEATURE_LABELS[item])) values.push(FEATURE_LABELS[item]);
      }
    }
    if (owner.halal_status === "fully_halal") values.unshift("Fully halal");
    else if (owner.halal_status === "halal_options") values.unshift("Halal options");
    return values.slice(0, 3);
  } catch {
    return [];
  }
}

export default function PlaceCard({ place, onSelect }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isFavorite, toggleFavorite } = useFavorites();
  const saved = isFavorite(place.id);
  const imageUrl = getPrimaryPlaceImage(place);
  const rating = place.rating !== null && place.rating !== undefined ? Number(place.rating) : null;
  const reviewCount = Number(place.review_count) || 0;
  const hasDistance = place.distance_km !== null && place.distance_km !== undefined;
  const featurePreview = getFeaturePreview(place);

  function stopCardClick(event) {
    event.stopPropagation();
  }

  function handleFavoriteClick(event) {
    event.stopPropagation();
    if (!user) {
      navigate("/login", { state: { from: window.location.pathname } });
      return;
    }
    toggleFavorite(place);
  }

  return (
    <article
      className="place-card"
      onClick={() => onSelect(place)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.target.closest("button, a")) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(place);
        }
      }}
    >
      <div className="place-image-wrapper">
        <img
          className="place-image"
          src={imageUrl}
          alt={`${place.name} business`}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={(event) => {
            event.currentTarget.onerror = null;
            event.currentTarget.src = getPlaceFallbackImage(place);
          }}
        />
        <div className="image-overlay" />
        {hasDistance && <span className="distance-badge">⌖ {place.distance_km} km</span>}
        <button type="button" className={saved ? "favorite-button saved" : "favorite-button"} aria-label={saved ? `Remove ${place.name} from favorites` : `Save ${place.name} to favorites`} aria-pressed={saved} onClick={handleFavoriteClick}>{saved ? "♥" : "♡"}</button>
      </div>

      <div className="place-content">
        <div className="place-heading-row">
          <p className="place-category">{place.category || "Local business"}</p>
          {place.verified && <span className="verified-badge-inline">✓ Verified</span>}
        </div>
        <h3>{place.name}</h3>
        <div className="rating-row">
          {rating !== null ? <><span className="rating-star">★</span><strong>{rating.toFixed(1)}</strong>{reviewCount > 0 && <span className="review-count">{reviewCount.toLocaleString()} reviews</span>}</> : <span className="review-count">No public rating yet</span>}
        </div>

        <div className="place-location-line"><span>⌖</span><span>{place.full_address || [place.city, place.state].filter(Boolean).join(", ") || "Location unavailable"}</span></div>

        {featurePreview.length > 0 && <div className="place-feature-preview">{featurePreview.map((feature) => <span key={feature}>{feature}</span>)}</div>}

        <div className="place-actions">
          <button type="button" className="place-action primary-action" onClick={(event) => { stopCardClick(event); onSelect(place); }}>View details</button>
          {place.phone_number && <a className="place-action secondary-action" href={`tel:${place.phone_number}`} onClick={stopCardClick}>Call</a>}
          {place.google_maps_url && <a className="place-action secondary-action" href={place.google_maps_url} target="_blank" rel="noreferrer" onClick={stopCardClick}>Directions</a>}
        </div>
      </div>
    </article>
  );
}
