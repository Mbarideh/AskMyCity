import { useEffect, useState } from "react";

import { getPlaces } from "../services/api";
import "./SearchBar.css";

const cities = [
  "",
  "Ottawa",
  "Nepean",
  "Kanata",
  "Orléans",
];

function SearchBar({ onSearch, onReset }) {
  const [searchText, setSearchText] = useState("");
  const [selectedCity, setSelectedCity] = useState("");

  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    const trimmedSearch = searchText.trim();

    if (trimmedSearch.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const results = await getPlaces({
          search: trimmedSearch,
          city: selectedCity,
        });

        setSuggestions(results.slice(0, 6));
        setShowSuggestions(true);
      } catch (error) {
        console.error("Could not load suggestions:", error);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchText, selectedCity]);

  function handleSubmit(event) {
    event.preventDefault();

    setShowSuggestions(false);

    onSearch({
      searchText: searchText.trim(),
      city: selectedCity,
    });
  }

  function handleReset() {
    setSearchText("");
    setSelectedCity("");
    setSuggestions([]);
    setShowSuggestions(false);

    onReset();
  }

  function handleSuggestionClick(place) {
    setSearchText(place.name);
    setSuggestions([]);
    setShowSuggestions(false);

    onSearch({
      searchText: place.name,
      city: selectedCity,
    });
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          type="text"
          placeholder="Search by business or category"
          value={searchText}
          onChange={(event) =>
            setSearchText(event.target.value)
          }
          onFocus={() => {
            if (suggestions.length > 0) {
              setShowSuggestions(true);
            }
          }}
        />

        {showSuggestions && (
          <div className="suggestions-list">
            {suggestions.length > 0 ? (
              suggestions.map((place) => (
                <button
                  key={place.id}
                  type="button"
                  className="suggestion-item"
                  onClick={() =>
                    handleSuggestionClick(place)
                  }
                >
                  <span className="suggestion-name">
                    {place.name}
                  </span>

                  <span className="suggestion-details">
                    {place.city || "Unknown city"} ·{" "}
                    {place.category}
                  </span>
                </button>
              ))
            ) : (
              <div className="no-suggestions">
                No matching businesses
              </div>
            )}
          </div>
        )}
      </div>

      <select
        className="city-select"
        value={selectedCity}
        onChange={(event) =>
          setSelectedCity(event.target.value)
        }
      >
        {cities.map((city) => (
          <option key={city || "all"} value={city}>
            {city || "All cities"}
          </option>
        ))}
      </select>

      <button type="submit" className="search-button">
        Search
      </button>

      <button
        type="button"
        className="reset-button"
        onClick={handleReset}
      >
        Reset
      </button>
    </form>
  );
}

export default SearchBar;