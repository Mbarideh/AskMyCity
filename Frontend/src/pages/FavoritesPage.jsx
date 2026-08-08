import { useNavigate } from "react-router-dom";

import PlaceCard from "../components/PlaceCard";
import PublicFooter from "../components/PublicFooter";
import PublicHeader from "../components/PublicHeader";
import useFavorites from "../hooks/useFavorites";
import "./FavoritesPage.css";

export default function FavoritesPage() {
  const navigate = useNavigate();
  const { favorites, favoritesLoading, favoritesError, reloadFavorites } = useFavorites();

  return (
    <div className="favorites-page-shell">
      <PublicHeader />
      <main className="favorites-page">
        <div className="favorites-container">
          <header className="favorites-header">
            <div><p className="favorites-kicker">SAVED FOR LATER</p><h1>Your places</h1><p>Keep restaurants and local businesses you want to revisit in one place.</p></div>
            {favorites.length > 0 && <span className="favorites-count-badge">{favorites.length} saved</span>}
          </header>

          {favoritesLoading && <section className="favorites-status"><div className="favorites-spinner" /><h2>Loading your saved places</h2></section>}
          {!favoritesLoading && favoritesError && <section className="favorites-status favorites-error"><h2>Saved places could not be loaded</h2><p>{favoritesError}</p><button type="button" onClick={reloadFavorites}>Try again</button></section>}
          {!favoritesLoading && !favoritesError && favorites.length === 0 && <section className="favorites-status"><div className="favorites-empty-icon">♡</div><h2>Nothing saved yet</h2><p>Use the heart button on any business to keep it here.</p><button type="button" onClick={() => navigate("/")}>Find a business</button></section>}
          {!favoritesLoading && favorites.length > 0 && <section className="favorites-grid" aria-label="Saved businesses">{favorites.map((place) => <PlaceCard key={place.id} place={place} onSelect={() => navigate(`/places/${place.id}`)} />)}</section>}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
