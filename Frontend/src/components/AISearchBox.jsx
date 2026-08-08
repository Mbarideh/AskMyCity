import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import useFavorites from "../hooks/useFavorites";
import BusinessMap from "./BusinessMap";
import PublicFooter from "./PublicFooter";
import PublicHeader from "./PublicHeader";
import { getPlaceFallbackImage, getPrimaryPlaceImage } from "../utils/placeImages";
import "./AISearchBox.css";

const STARTER_PROMPTS = [
  { icon: "🥘", title: "Halal nearby", prompt: "Find halal restaurants near me" },
  { icon: "👨‍👩‍👧", title: "Family dinner", prompt: "Find family-friendly restaurants near me" },
  { icon: "🅿️", title: "Easy parking", prompt: "Find Italian restaurants with parking" },
  { icon: "🔧", title: "Home repair", prompt: "Find a highly rated plumber near me" },
];

const CATEGORY_PROMPTS = [
  { icon: "🍽️", label: "Restaurants", prompt: "Find restaurants near me" },
  { icon: "🔧", label: "Plumbers", prompt: "Find plumbers near me" },
  { icon: "⚡", label: "Electricians", prompt: "Find electricians near me" },
  { icon: "🦷", label: "Dentists", prompt: "Find dentists near me" },
  { icon: "☕", label: "Coffee", prompt: "Find coffee shops near me" },
  { icon: "🌿", label: "Patios", prompt: "Find restaurants with a patio near me" },
];

const SEARCH_STEPS = [
  "Reading your request",
  "Checking local records",
  "Applying your requested filters",
  "Ranking the matching places",
];

function buildSearchSummary(results, explanation, filters = {}) {
  const count = results.length;
  const plan = filters.search_plan || filters.plan || {};
  const radius = plan.radius_used_km || plan.final_radius_km || filters.radius_used_km;
  const expanded = Boolean(plan.radius_expanded || filters.radius_expanded);

  if (expanded && radius) {
    return `Search expanded to ${radius} km to find ${count} matching option${count === 1 ? "" : "s"}.`;
  }
  if (radius) {
    return `${count} matching option${count === 1 ? "" : "s"} found within ${radius} km.`;
  }
  return explanation || `${count} local option${count === 1 ? "" : "s"} matched your request.`;
}

function formatPrice(priceRange) {
  if (!priceRange) return null;
  const normalized = String(priceRange).trim();
  if (!normalized) return null;
  return normalized.length <= 5 ? normalized : normalized.slice(0, 18);
}

function buildFallbackReasons(place, filters = {}) {
  const reasons = [];
  const rating = Number(place.rating) || 0;
  const reviews = Number(place.review_count) || 0;
  const distance = Number(place.distance_km);

  if (Number.isFinite(distance)) reasons.push(`${distance} km from your location`);
  if (rating > 0) reasons.push(`${rating.toFixed(1)}★ rating${reviews ? ` from ${reviews.toLocaleString()} reviews` : ""}`);
  if (place.verified) reasons.push("Verified business information");
  if (filters.search) reasons.push(`Matches “${filters.search}”`);
  if (!reasons.length && place.city) reasons.push(`Located in ${place.city}`);
  if (!reasons.length && place.category) reasons.push(`${place.category} business`);

  return reasons.slice(0, 3);
}

function ResultCard({ place, rank, onSelect, filters, saved, onToggleSaved }) {
  const rating = Number(place.rating);
  const reviewCount = Number(place.review_count) || 0;
  const hasDistance = place.distance_km !== null && place.distance_km !== undefined;
  const reasons = Array.isArray(place.match_reasons) && place.match_reasons.length
    ? place.match_reasons.slice(0, 4)
    : buildFallbackReasons(place, filters);
  const [imageSource, setImageSource] = useState(getPrimaryPlaceImage(place));
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    setImageSource(getPrimaryPlaceImage(place));
    setImageLoaded(false);
  }, [place]);

  function stopPropagation(event) {
    event.stopPropagation();
  }

  return (
    <article
      className="local-result-card"
      onClick={() => onSelect(place)}
      onKeyDown={(event) => {
        if (event.target.closest("a, button")) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(place);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className={`local-result-image-wrap ${imageLoaded ? "loaded" : ""}`}>
        <img
          src={imageSource}
          alt={place.name}
          className="local-result-image"
          referrerPolicy="no-referrer"
          loading="lazy"
          onLoad={() => setImageLoaded(true)}
          onError={() => {
            setImageSource(getPlaceFallbackImage(place));
            setImageLoaded(true);
          }}
        />
        <span className="local-result-rank">#{rank}</span>
        <button
          type="button"
          className={`local-result-save ${saved ? "saved" : ""}`}
          onClick={(event) => {
            stopPropagation(event);
            onToggleSaved(place);
          }}
          aria-label={saved ? `Remove ${place.name} from favorites` : `Save ${place.name}`}
          aria-pressed={saved}
        >
          {saved ? "♥" : "♡"}
        </button>
      </div>

      <div className="local-result-content">
        <div className="local-result-title-row">
          <div>
            <p className="local-result-category">{place.cuisine || place.subcategory || place.category || "Local business"}</p>
            <h3>{place.name}</h3>
          </div>
          {place.verified ? (
            <span className="local-trust-pill">✓ Verified</span>
          ) : place.enrichment_status === "enriched" ? (
            <span className="local-source-pill">Evidence checked</span>
          ) : null}
        </div>

        <div className="local-result-meta">
          {rating > 0 && <span className="local-rating">★ {rating.toFixed(1)}</span>}
          {reviewCount > 0 && <span>{reviewCount.toLocaleString()} reviews</span>}
          {hasDistance && <span>⌖ {place.distance_km} km</span>}
          {place.price_range && <span>{formatPrice(place.price_range)}</span>}
        </div>

        {reasons.length > 0 && (
          <div className="local-match-reasons">
            <strong>Why it matches</strong>
            <ul>
              {reasons.map((reason, index) => (
                <li key={`${reason}-${index}`}><span>✓</span>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="local-result-actions">
          <button type="button" className="local-primary-action" onClick={() => onSelect(place)}>View details</button>
          {place.phone_number && <a href={`tel:${place.phone_number}`} onClick={stopPropagation}>Call</a>}
          {place.google_maps_url && <a href={place.google_maps_url} target="_blank" rel="noreferrer" onClick={stopPropagation}>Directions</a>}
        </div>
      </div>
    </article>
  );
}

function SearchProgress({ locationMessage }) {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStep((current) => Math.min(current + 1, SEARCH_STEPS.length - 1));
    }, 1100);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="local-search-progress" aria-live="polite">
      <div className="local-progress-heading">
        <span className="local-progress-spinner" />
        <div><strong>{locationMessage || "Searching your city…"}</strong><small>Using the filters in your request.</small></div>
      </div>
      <div className="local-progress-steps">
        {SEARCH_STEPS.map((step, index) => (
          <span key={step} className={index < activeStep ? "done" : index === activeStep ? "active" : ""}>
            {index < activeStep ? "✓" : index + 1} {step}
          </span>
        ))}
      </div>
    </div>
  );
}

function SearchComposer({ query, setQuery, submitQuery, loading, compact = false, inputRef }) {
  return (
    <form
      className={`local-search-composer ${compact ? "compact" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        submitQuery(query);
      }}
    >
      <span className="local-search-icon" aria-hidden="true">⌕</span>
      <input
        ref={inputRef}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={compact ? "Refine your search or ask a follow-up…" : "Try “halal restaurant near me” or “plumber open now”"}
        maxLength={1000}
        disabled={loading}
        aria-label="Search AskMyCity"
      />
      <button type="submit" disabled={loading || query.trim().length < 3}>
        {loading ? <span className="local-button-spinner" /> : compact ? "Search" : "Find places"}
      </button>
    </form>
  );
}

export default function AISearchBox({
  onSearch,
  onNewChat,
  onPlaceSelect,
  messages = [],
  loading = false,
  locationMessage = "",
}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isFavorite, toggleFavorite } = useFavorites();
  const [query, setQuery] = useState("");
  const [resultViews, setResultViews] = useState({});
  const messagesEndRef = useRef(null);
  const searchInputRef = useRef(null);

  const hasConversation = messages.length > 0;
  const recentSearches = useMemo(
    () => messages.filter((message) => message.role === "user").map((message) => message.content).reverse().slice(0, 4),
    [messages]
  );

  useEffect(() => {
    if (hasConversation) messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, locationMessage, hasConversation]);

  function submitQuery(value) {
    const cleanedQuery = String(value || "").trim();
    if (cleanedQuery.length < 3 || loading) return;
    onSearch(cleanedQuery);
    setQuery("");
  }

  function handleNewSearch() {
    if (loading) return;
    setQuery("");
    setResultViews({});
    onNewChat();
    window.scrollTo({ top: 0, behavior: "smooth" });
    window.setTimeout(() => searchInputRef.current?.focus(), 150);
  }

  async function toggleSaved(place) {
    if (!user) {
      navigate("/login");
      return;
    }
    await toggleFavorite(place);
  }

  return (
    <div className="local-discovery-page">
      <PublicHeader />

      {!hasConversation ? (
        <>
          <main className="local-home-main">
            <section className="local-hero">
              <div className="local-hero-copy">
                <p className="local-eyebrow"><span /> LOCAL DISCOVERY, MADE PERSONAL</p>
                <h1>Find the right local place for <em>what you actually need.</em></h1>
                <p className="local-hero-description">
                  Search restaurants and local services by distance, parking, family needs, dietary options, amenities, and more — not just by rating.
                </p>
                <SearchComposer query={query} setQuery={setQuery} submitQuery={submitQuery} loading={loading} inputRef={searchInputRef} />
                <div className="local-search-hints">
                  <span>Popular:</span>
                  <button type="button" onClick={() => submitQuery("Find halal restaurants near me")}>Halal nearby</button>
                  <button type="button" onClick={() => submitQuery("Find family-friendly restaurants near me")}>Family-friendly</button>
                  <button type="button" onClick={() => submitQuery("Find restaurants with free parking near me")}>Free parking</button>
                </div>
              </div>

              <aside className="local-hero-board" aria-label="Examples of local searches">
                <div className="local-board-topline"><span>⌖</span><strong>Search like a local</strong><small>Tell us what matters</small></div>
                <div className="local-board-grid">
                  {STARTER_PROMPTS.map((item) => (
                    <button type="button" key={item.prompt} onClick={() => submitQuery(item.prompt)}>
                      <span>{item.icon}</span><div><strong>{item.title}</strong><small>{item.prompt}</small></div><b>→</b>
                    </button>
                  ))}
                </div>
                <div className="local-board-note"><span>✓</span><p><strong>Transparent results</strong><br />See distance, evidence, and the exact reasons a place matched.</p></div>
              </aside>
            </section>

            <section className="local-category-section">
              <div className="local-section-heading">
                <div><p>START EXPLORING</p><h2>What are you looking for?</h2></div>
                <button type="button" onClick={() => navigate("/explore")}>Browse all businesses <span>→</span></button>
              </div>
              <div className="local-category-grid">
                {CATEGORY_PROMPTS.map((item) => (
                  <button key={item.label} type="button" onClick={() => submitQuery(item.prompt)}>
                    <span>{item.icon}</span><strong>{item.label}</strong><small>Search nearby</small>
                  </button>
                ))}
              </div>
            </section>

            <section className="local-value-strip">
              <div><span>⌖</span><strong>Distance-aware</strong><p>Near-me searches use your actual location when you allow it.</p></div>
              <div><span>✓</span><strong>Specific filters</strong><p>Halal, parking, family-friendly, patio, and other details stay part of the search.</p></div>
              <div><span>↻</span><strong>Gets smarter over time</strong><p>Saved business knowledge can be reused instead of researching the same fact again.</p></div>
            </section>
          </main>
          <PublicFooter />
        </>
      ) : (
        <main className="local-results-main">
          <section className="local-results-toolbar">
            <div>
              <p className="local-eyebrow"><span /> YOUR LOCAL SEARCH</p>
              <h1>Results and follow-ups</h1>
            </div>
            <button type="button" className="local-new-search" onClick={handleNewSearch} disabled={loading}>New search</button>
          </section>

          <div className="local-top-search">
            <SearchComposer query={query} setQuery={setQuery} submitQuery={submitQuery} loading={loading} compact inputRef={searchInputRef} />
            {recentSearches.length > 1 && (
              <div className="local-recent-line"><span>Recent in this search:</span>{recentSearches.slice(0, 3).map((search, index) => <button type="button" key={`${search}-${index}`} onClick={() => submitQuery(search)}>{search}</button>)}</div>
            )}
          </div>

          <section className="local-conversation-stream" aria-live="polite">
            {messages.map((message, index) => {
              const isAssistant = message.role === "assistant";
              const messageResults = Array.isArray(message.results) ? message.results : [];
              const messageExplanation = message.explanation || "";
              const messageUrgency = message.urgency || "";
              const messageFilters = message.filters || {};
              const messageView = resultViews[index] || "list";

              if (!isAssistant) {
                return (
                  <div className="local-query-turn" key={`${message.role}-${index}-${message.content.slice(0, 16)}`}>
                    <span>Your search</span><strong>{message.content}</strong>
                  </div>
                );
              }

              return (
                <article className="local-answer-turn" key={`${message.role}-${index}-${message.content.slice(0, 16)}`}>
                  <div className="local-answer-summary">
                    <div className="local-answer-mark" aria-hidden="true">A</div>
                    <div><span>AskMyCity</span><p>{message.content}</p></div>
                  </div>

                  {messageResults.length > 0 && (
                    <div className="local-results-block">
                      <div className="local-results-heading">
                        <div><p>MATCHING PLACES</p><h2>{messageResults.length} local option{messageResults.length === 1 ? "" : "s"}</h2><span>{buildSearchSummary(messageResults, messageExplanation, messageFilters)}</span></div>
                        <div className="local-results-controls">
                          {messageUrgency && messageUrgency !== "normal" && <span className={`local-urgency urgency-${messageUrgency}`}>{messageUrgency}</span>}
                          <div className="local-view-toggle">
                            <button type="button" className={messageView === "list" ? "active" : ""} onClick={() => setResultViews((current) => ({ ...current, [index]: "list" }))}>List</button>
                            <button type="button" className={messageView === "map" ? "active" : ""} onClick={() => setResultViews((current) => ({ ...current, [index]: "map" }))}>Map</button>
                          </div>
                        </div>
                      </div>

                      {messageView === "list" ? (
                        <div className="local-result-grid">
                          {messageResults.map((place, placeIndex) => (
                            <ResultCard
                              key={`${place.id}-${placeIndex}`}
                              place={place}
                              rank={placeIndex + 1}
                              onSelect={onPlaceSelect}
                              filters={messageFilters}
                              saved={isFavorite(place.id)}
                              onToggleSaved={toggleSaved}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="local-map-frame"><BusinessMap businesses={messageResults} onBusinessSelect={onPlaceSelect} /></div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}

            {loading && <SearchProgress locationMessage={locationMessage} />}
            {!loading && locationMessage && <div className="local-location-note"><span>⌖</span>{locationMessage}</div>}
            <div ref={messagesEndRef} />
          </section>

          <section className="local-followup-dock">
            <div><strong>Want to narrow it down?</strong><span>Ask for more, change the radius, or add another condition.</span></div>
            <SearchComposer query={query} setQuery={setQuery} submitQuery={submitQuery} loading={loading} compact />
          </section>
        </main>
      )}
    </div>
  );
}
