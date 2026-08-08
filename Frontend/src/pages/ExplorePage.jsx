import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import PlaceCard from "../components/PlaceCard";
import PublicFooter from "../components/PublicFooter";
import PublicHeader from "../components/PublicHeader";
import { getExplorePlaces } from "../services/api";
import "./ExplorePage.css";

const ALL_CATEGORIES = "All categories";

function normalizeText(value) {
  return String(value || "").trim();
}

export default function ExplorePage() {
  const navigate = useNavigate();
  const [places, setPlaces] = useState([]);
  const [allCategories, setAllCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadBusinesses(overrides = {}) {
    const nextSearch = overrides.search ?? search;
    const nextCity = overrides.city ?? city;
    const nextCategory = overrides.category ?? category;

    try {
      setLoading(true);
      setError("");
      const data = await getExplorePlaces({
        search: normalizeText(nextSearch),
        city: normalizeText(nextCity),
        category: nextCategory === ALL_CATEGORIES ? "" : normalizeText(nextCategory),
        limit: 90,
      });
      const rows = Array.isArray(data) ? data : [];
      setPlaces(rows);
      if (!normalizeText(nextSearch) && !normalizeText(nextCity) && nextCategory === ALL_CATEGORIES) {
        setAllCategories(Array.from(new Set(rows.map((place) => normalizeText(place.category)).filter(Boolean))).sort((a, b) => a.localeCompare(b)));
      }
    } catch (requestError) {
      console.error("Explore could not load businesses:", requestError);
      setPlaces([]);
      setError(requestError.message || "Explore could not load businesses.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBusinesses({ search: "", city: "", category: ALL_CATEGORIES });
    // Initial database load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const categories = useMemo(() => [ALL_CATEGORIES, ...allCategories], [allCategories]);

  function handleSubmit(event) {
    event.preventDefault();
    loadBusinesses();
  }

  function clearFilters() {
    setSearch("");
    setCity("");
    setCategory(ALL_CATEGORIES);
    loadBusinesses({ search: "", city: "", category: ALL_CATEGORIES });
  }

  return (
    <div className="explore-page-shell">
      <PublicHeader />
      <main className="explore-page">
        <div className="explore-container">
          <header className="explore-header">
            <div>
              <p className="explore-kicker">BROWSE THE CITY</p>
              <h1>Explore local businesses</h1>
              <p>Browse the directory directly when you already know the type of place you want. Use Discover when your request has multiple conditions.</p>
            </div>
            <button type="button" className="explore-smart-search" onClick={() => navigate("/")}>Try a smart search <span>→</span></button>
          </header>

          <form className="explore-filters" onSubmit={handleSubmit}>
            <label className="explore-search-field">
              <span>Search</span>
              <div><b aria-hidden="true">⌕</b><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Business name, service, or address" /></div>
            </label>
            <label><span>City</span><input type="text" value={city} onChange={(event) => setCity(event.target.value)} placeholder="Ottawa" /></label>
            <label><span>Category</span><select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            <div className="explore-filter-actions"><button type="submit">Show results</button><button type="button" className="secondary" onClick={clearFilters}>Clear</button></div>
          </form>

          <section className="explore-summary" aria-live="polite">
            <div><strong>{loading ? "Loading…" : `${places.length} business${places.length === 1 ? "" : "es"}`}</strong><span>{search || city || category !== ALL_CATEGORIES ? "matching your filters" : "available to explore"}</span></div>
            {!loading && !error && <small>Sorted by rating and review count.</small>}
          </section>

          {loading && <section className="explore-status"><div className="explore-spinner" /><h2>Loading local businesses</h2><p>Getting the latest records from AskMyCity.</p></section>}
          {!loading && error && <section className="explore-status explore-error"><h2>Explore could not be loaded</h2><p>{error}</p><button type="button" onClick={() => loadBusinesses()}>Try again</button></section>}
          {!loading && !error && places.length === 0 && <section className="explore-status"><div className="explore-empty-icon">⌖</div><h2>No matching businesses</h2><p>Try a broader name, city, or category.</p><button type="button" onClick={clearFilters}>Show all businesses</button></section>}
          {!loading && !error && places.length > 0 && <section className="explore-grid" aria-label="Explore businesses">{places.map((place) => <PlaceCard key={place.id} place={place} onSelect={() => navigate(`/places/${place.id}`)} />)}</section>}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
