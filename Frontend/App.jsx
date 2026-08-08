import { useEffect, useState } from "react";
import {
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import AISearchBox from "./components/AISearchBox";
import BusinessMap from "./components/BusinessMap";
import Header from "./components/Header";
import PlaceCard from "./components/PlaceCard";
import PlaceDetails from "./components/PlaceDetails";
import PopularCategories from "./components/PopularCategories";
import SearchBar from "./components/SearchBar";

import {
  getPlaces,
  searchWithAI,
} from "./services/api";

import "./App.css";


const MAX_CONVERSATION_MESSAGES = 20;


function PlacesPage() {
  const navigate = useNavigate();

  const [places, setPlaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiLoading, setAiLoading] =
    useState(false);

  const [aiExplanation, setAiExplanation] =
    useState("");

  const [
    aiAssistantMessage,
    setAiAssistantMessage,
  ] = useState("");

  const [aiUrgency, setAiUrgency] =
    useState("");

  const [aiMessages, setAiMessages] =
    useState([]);

  const [
    savedUserLocation,
    setSavedUserLocation,
  ] = useState(null);

  const [currentSearch, setCurrentSearch] =
    useState("");

  const [selectedCity, setSelectedCity] =
    useState("");

  const [activeCategory, setActiveCategory] =
    useState("");

  const [viewMode, setViewMode] =
    useState("list");

  const [locationMessage, setLocationMessage] =
    useState("");


  async function loadPlaces({
    search = currentSearch,
    city = selectedCity,
    category = activeCategory,
  } = {}) {
    try {
      setLoading(true);
      setError("");
      setLocationMessage("");
      setAiExplanation("");
      setAiAssistantMessage("");
      setAiUrgency("");

      const data = await getPlaces({
        search,
        city,
        category,
      });

      setPlaces(
        Array.isArray(data)
          ? data
          : []
      );
    } catch (requestError) {
      console.error(
        "Could not load businesses:",
        requestError
      );

      setError(
        requestError.message ||
        "Could not load businesses."
      );

      setPlaces([]);
    } finally {
      setLoading(false);
    }
  }


  function queryUsesNearMe(query) {
    if (typeof query !== "string") {
      return false;
    }

    const normalizedQuery =
      query.toLowerCase().trim();

    const nearMePatterns = [
      /\bnear\s+me\b/i,
      /\bnearby\b/i,
      /\bclose\s+to\s+me\b/i,
      /\bclosest\s+to\s+me\b/i,
      /\baround\s+me\b/i,
      /\bin\s+my\s+area\b/i,
    ];

    return nearMePatterns.some(
      (pattern) =>
        pattern.test(normalizedQuery)
    );
  }


  function conversationUsesNearMe(
    currentQuery
  ) {
    if (queryUsesNearMe(currentQuery)) {
      return true;
    }

    return aiMessages.some(
      (message) =>
        message.role === "user" &&
        queryUsesNearMe(message.content)
    );
  }


  function getCurrentLocation() {
    return new Promise(
      (resolve, reject) => {
        if (!navigator.geolocation) {
          reject(
            new Error(
              "Your browser does not support location services. Please enter a city instead."
            )
          );

          return;
        }

        navigator.geolocation.getCurrentPosition(
          (position) => {
            resolve({
              latitude:
                position.coords.latitude,
              longitude:
                position.coords.longitude,
            });
          },

          (locationError) => {
            if (
              locationError.code ===
              locationError.PERMISSION_DENIED
            ) {
              reject(
                new Error(
                  "Location permission was denied. Please allow location access in your browser or enter a city such as Ottawa or Nepean."
                )
              );

              return;
            }

            if (
              locationError.code ===
              locationError.POSITION_UNAVAILABLE
            ) {
              reject(
                new Error(
                  "Your current location could not be determined. Please enter a city instead."
                )
              );

              return;
            }

            if (
              locationError.code ===
              locationError.TIMEOUT
            ) {
              reject(
                new Error(
                  "Location detection timed out. Please try again or enter a city."
                )
              );

              return;
            }

            reject(
              new Error(
                "Your current location could not be accessed. Please enter a city instead."
              )
            );
          },

          {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 300000,
          }
        );
      }
    );
  }


  function createConversationMessages(
    userQuery,
    assistantMessage
  ) {
    const nextMessages = [
      ...aiMessages,
      {
        role: "user",
        content: userQuery,
      },
      {
        role: "assistant",
        content: assistantMessage,
      },
    ];

    return nextMessages.slice(
      -MAX_CONVERSATION_MESSAGES
    );
  }


  async function handleAISearch(query) {
    const normalizedQuery = String(
      query || ""
    ).trim();

    if (normalizedQuery.length < 3) {
      setError(
        "Please enter a longer search request."
      );

      return;
    }

    try {
      setAiLoading(true);
      setLoading(true);
      setError("");
      setLocationMessage("");
      setAiExplanation("");
      setAiAssistantMessage("");
      setAiUrgency("");
      setViewMode("list");

      const needsUserLocation =
        conversationUsesNearMe(
          normalizedQuery
        );

      let userLocation = null;

      if (needsUserLocation) {
        if (savedUserLocation) {
          userLocation =
            savedUserLocation;

          setLocationMessage(
            "Using your saved location to search nearby businesses..."
          );
        } else {
          setLocationMessage(
            "Waiting for your location permission..."
          );

          userLocation =
            await getCurrentLocation();

          setSavedUserLocation(
            userLocation
          );

          setLocationMessage(
            "Location found. Searching for nearby businesses..."
          );
        }
      }

      const data = await searchWithAI(
        normalizedQuery,
        userLocation,
        aiMessages
      );

      const results = Array.isArray(
        data.results
      )
        ? data.results
        : [];

      const assistantMessage =
        data.assistant_message ||
        data.filters?.explanation ||
        "I searched for matching businesses.";

      setPlaces(results);

      setCurrentSearch(
        normalizedQuery
      );

      setSelectedCity(
        data.filters?.city || ""
      );

      setActiveCategory(
        data.filters?.category || ""
      );

      setAiExplanation(
        data.filters?.explanation || ""
      );

      setAiAssistantMessage(
        assistantMessage
      );

      setAiUrgency(
        data.filters?.urgency || ""
      );

      setAiMessages(
        createConversationMessages(
          normalizedQuery,
          assistantMessage
        )
      );

      if (
        needsUserLocation &&
        userLocation &&
        results.length > 0
      ) {
        setLocationMessage(
          "Results are sorted by distance from your current location."
        );
      } else {
        setLocationMessage("");
      }
    } catch (requestError) {
      console.error(
        "AI search failed:",
        requestError
      );

      setError(
        requestError.message ||
        "AI search is temporarily unavailable."
      );

      setPlaces([]);
      setLocationMessage("");
    } finally {
      setAiLoading(false);
      setLoading(false);
    }
  }


  function clearAIConversation() {
    setAiMessages([]);
    setAiExplanation("");
    setAiAssistantMessage("");
    setAiUrgency("");
  }


  function handleSearch({
    searchText,
    city,
  }) {
    setCurrentSearch(searchText);
    setSelectedCity(city);
    setActiveCategory("");
    setLocationMessage("");

    clearAIConversation();

    loadPlaces({
      search: searchText,
      city,
      category: "",
    });
  }


  function handleReset() {
    setCurrentSearch("");
    setSelectedCity("");
    setActiveCategory("");
    setLocationMessage("");
    setViewMode("list");
    setSavedUserLocation(null);

    clearAIConversation();

    loadPlaces({
      search: "",
      city: "",
      category: "",
    });
  }


  function handleCategorySelect(category) {
    const nextCategory =
      activeCategory === category
        ? ""
        : category;

    setActiveCategory(nextCategory);
    setLocationMessage("");

    clearAIConversation();

    loadPlaces({
      search: currentSearch,
      city: selectedCity,
      category: nextCategory,
    });
  }


  function handlePlaceSelect(place) {
    navigate(
      `/places/${place.id}`
    );
  }


  useEffect(() => {
    loadPlaces({
      search: "",
      city: "",
      category: "",
    });
  }, []);


  let resultTitle =
    "Recommended businesses";

  if (
    aiAssistantMessage ||
    aiExplanation
  ) {
    resultTitle =
      "AI recommendations";
  } else if (
    currentSearch &&
    selectedCity
  ) {
    resultTitle =
      `Results for “${currentSearch}” in ${selectedCity}`;
  } else if (currentSearch) {
    resultTitle =
      `Results for “${currentSearch}”`;
  } else if (
    activeCategory &&
    selectedCity
  ) {
    resultTitle =
      `${activeCategory} businesses in ${selectedCity}`;
  } else if (activeCategory) {
    resultTitle =
      `${activeCategory} businesses`;
  } else if (selectedCity) {
    resultTitle =
      `Businesses in ${selectedCity}`;
  }


  return (
    <div className="app-shell">
      <section className="hero">
        <div className="hero-overlay">
          <Header />

          <SearchBar
            onSearch={handleSearch}
            onReset={handleReset}
          />

          <PopularCategories
            activeCategory={
              activeCategory
            }
            onCategorySelect={
              handleCategorySelect
            }
          />

          <p className="hero-note">
            Search trusted local businesses by
            name, city, or category.
          </p>

          <AISearchBox
            onSearch={handleAISearch}
            loading={aiLoading}
          />
        </div>
      </section>

      <main className="content">
        <div className="results-header">
          <div>
            <p className="eyebrow">
              {
                aiAssistantMessage ||
                aiExplanation
                  ? "AI CONCIERGE"
                  : "LOCAL SERVICES"
              }
            </p>

            <h2>{resultTitle}</h2>

            {locationMessage && (
              <div className="location-message">
                <span aria-hidden="true">
                  📍
                </span>

                <p>{locationMessage}</p>
              </div>
            )}

            {(
              aiAssistantMessage ||
              aiExplanation
            ) && (
              <div className="ai-result-summary">
                <span className="ai-summary-icon">
                  ✦
                </span>

                <div>
                  {aiAssistantMessage && (
                    <p>
                      {aiAssistantMessage}
                    </p>
                  )}

                  {aiExplanation &&
                    aiExplanation !==
                      aiAssistantMessage && (
                      <p>
                        {aiExplanation}
                      </p>
                    )}

                  {aiUrgency && (
                    <span
                      className={
                        `urgency-badge urgency-${aiUrgency}`
                      }
                    >
                      {aiUrgency}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {!loading && !error && (
            <span className="result-count">
              {places.length} result
              {
                places.length === 1
                  ? ""
                  : "s"
              }
            </span>
          )}
        </div>

        {!loading &&
          !error &&
          places.length > 0 && (
            <div className="view-toggle">
              <button
                type="button"
                className={
                  viewMode === "list"
                    ? "view-toggle-button active"
                    : "view-toggle-button"
                }
                onClick={() =>
                  setViewMode("list")
                }
              >
                List
              </button>

              <button
                type="button"
                className={
                  viewMode === "map"
                    ? "view-toggle-button active"
                    : "view-toggle-button"
                }
                onClick={() =>
                  setViewMode("map")
                }
              >
                Map
              </button>
            </div>
          )}

        {loading && (
          <div className="status-card">
            <div className="spinner" />

            <p>
              {
                locationMessage ||
                (
                  aiLoading
                    ? "The AI is finding the best businesses..."
                    : "Loading businesses..."
                )
              }
            </p>
          </div>
        )}

        {error && (
          <div className="status-card error-card">
            <h3>
              Something went wrong
            </h3>

            <p>{error}</p>

            <button
              type="button"
              className="retry-button"
              onClick={handleReset}
            >
              Return to all businesses
            </button>
          </div>
        )}

        {!loading &&
          !error &&
          places.length === 0 && (
            <div className="status-card">
              <h3>
                No businesses found
              </h3>

              <p>
                Try describing your request in
                another way, entering a city, or
                removing one of the requirements.
              </p>
            </div>
          )}

        {!loading &&
          !error &&
          places.length > 0 &&
          viewMode === "list" && (
            <section className="places-grid">
              {places.map((place) => (
                <PlaceCard
                  key={place.id}
                  place={place}
                  onSelect={
                    handlePlaceSelect
                  }
                />
              ))}
            </section>
          )}

        {!loading &&
          !error &&
          places.length > 0 &&
          viewMode === "map" && (
            <BusinessMap
              businesses={places}
              onBusinessSelect={
                handlePlaceSelect
              }
            />
          )}
      </main>
    </div>
  );
}


function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={<PlacesPage />}
      />

      <Route
        path="/places/:placeId"
        element={<PlaceDetails />}
      />

      <Route
        path="*"
        element={<PlacesPage />}
      />
    </Routes>
  );
}


export default App;