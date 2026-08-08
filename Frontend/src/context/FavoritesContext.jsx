import { createContext, useCallback, useContext, useMemo, useState, useEffect } from "react";

import { useAuth } from "./AuthContext";
import { addFavorite as addFavoriteRequest, getFavorites, removeFavorite as removeFavoriteRequest } from "../services/api";

const FavoritesContext = createContext(null);

export function FavoritesProvider({ children }) {
  const { token } = useAuth();
  const [favorites, setFavorites] = useState([]);
  const [favoritesLoading, setFavoritesLoading] = useState(Boolean(token));
  const [favoritesError, setFavoritesError] = useState("");

  const loadFavorites = useCallback(async () => {
    if (!token) {
      setFavorites([]);
      setFavoritesLoading(false);
      setFavoritesError("");
      return [];
    }
    try {
      setFavoritesLoading(true);
      setFavoritesError("");
      const data = await getFavorites(token);
      const safe = Array.isArray(data) ? data : [];
      setFavorites(safe);
      return safe;
    } catch (error) {
      console.error("Could not load favorites:", error);
      setFavoritesError(error.message || "Could not load favorites.");
      return [];
    } finally {
      setFavoritesLoading(false);
    }
  }, [token]);

  useEffect(() => { loadFavorites(); }, [loadFavorites]);

  const favoriteIds = useMemo(() => new Set(favorites.map((favorite) => String(favorite.id))), [favorites]);
  const isFavorite = useCallback((placeId) => favoriteIds.has(String(placeId)), [favoriteIds]);

  const addFavorite = useCallback(async (place) => {
    if (!token) {
      setFavoritesError("Please sign in to save businesses.");
      return false;
    }
    if (!place?.id || favoriteIds.has(String(place.id))) return true;
    const previous = favorites;
    setFavorites([place, ...favorites]);
    try {
      setFavoritesError("");
      const savedPlace = await addFavoriteRequest(token, place.id);
      setFavorites((current) => [savedPlace, ...current.filter((favorite) => String(favorite.id) !== String(savedPlace.id))]);
      return true;
    } catch (error) {
      setFavorites(previous);
      setFavoritesError(error.message || "Could not save this business.");
      return false;
    }
  }, [token, favoriteIds, favorites]);

  const removeFavorite = useCallback(async (placeId) => {
    if (!token) {
      setFavoritesError("Please sign in to manage favorites.");
      return false;
    }
    const previous = favorites;
    setFavorites((current) => current.filter((favorite) => String(favorite.id) !== String(placeId)));
    try {
      setFavoritesError("");
      await removeFavoriteRequest(token, placeId);
      return true;
    } catch (error) {
      setFavorites(previous);
      setFavoritesError(error.message || "Could not remove this business.");
      return false;
    }
  }, [token, favorites]);

  const toggleFavorite = useCallback(async (place) => {
    if (!place?.id) return false;
    return favoriteIds.has(String(place.id)) ? removeFavorite(place.id) : addFavorite(place);
  }, [favoriteIds, removeFavorite, addFavorite]);

  const clearFavorites = useCallback(async () => {
    const ids = favorites.map((favorite) => favorite.id);
    const results = await Promise.all(ids.map((id) => removeFavorite(id)));
    return results.every(Boolean);
  }, [favorites, removeFavorite]);

  const value = useMemo(() => ({
    favorites,
    favoriteCount: favorites.length,
    favoritesLoading,
    favoritesError,
    isFavorite,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    clearFavorites,
    reloadFavorites: loadFavorites,
  }), [favorites, favoritesLoading, favoritesError, isFavorite, addFavorite, removeFavorite, toggleFavorite, clearFavorites, loadFavorites]);

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavoritesContext() {
  const value = useContext(FavoritesContext);
  if (!value) throw new Error("useFavorites must be used inside FavoritesProvider.");
  return value;
}
