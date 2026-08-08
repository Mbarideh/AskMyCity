import { useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";

import AISearchBox from "./components/AISearchBox";
import PlaceDetails from "./components/PlaceDetails";
import { searchWithAI } from "./services/api";

import "./App.css";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ProtectedRoute from "./pages/dashboard/ProtectedRoute";
import DashboardPage from "./pages/dashboard/DashboardPage";
import ProfilePage from "./pages/dashboard/ProfilePage";
import MenuPage from "./pages/dashboard/MenuPage";
import ReviewsPage from "./pages/dashboard/ReviewsPage";
import FavoritesPage from "./pages/FavoritesPage";
import ExplorePage from "./pages/ExplorePage";

const MAX_CONVERSATION_MESSAGES = 20;

function PlacesPage() {
  const navigate = useNavigate();

  const [aiLoading, setAiLoading] = useState(false);
  const [aiMessages, setAiMessages] = useState([]);
  const [savedUserLocation, setSavedUserLocation] = useState(null);
  const [locationMessage, setLocationMessage] = useState("");

  function queryUsesNearMe(query) {
    if (typeof query !== "string") return false;

    const nearMePatterns = [
      /\bnear\s+me\b/i,
      /\bnearby\b/i,
      /\bclose\s+to\s+me\b/i,
      /\bclosest\s+to\s+me\b/i,
      /\baround\s+me\b/i,
      /\bin\s+my\s+area\b/i,
    ];

    return nearMePatterns.some((pattern) => pattern.test(query.trim()));
  }

  function conversationUsesNearMe(currentQuery, conversation) {
    if (queryUsesNearMe(currentQuery)) return true;

    return conversation.some(
      (message) => message.role === "user" && queryUsesNearMe(message.content)
    );
  }

  function getCurrentLocation() {
    return new Promise((resolve, reject) => {
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
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
        },
        (locationError) => {
          if (locationError.code === locationError.PERMISSION_DENIED) {
            reject(
              new Error(
                "Location permission was denied. Allow location access or enter a city such as Ottawa or Nepean."
              )
            );
            return;
          }

          if (locationError.code === locationError.POSITION_UNAVAILABLE) {
            reject(
              new Error(
                "Your current location could not be determined. Please enter a city instead."
              )
            );
            return;
          }

          if (locationError.code === locationError.TIMEOUT) {
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
    });
  }

  async function handleAISearch(query) {
    const normalizedQuery = String(query || "").trim();

    if (normalizedQuery.length < 3 || aiLoading) return;

    const previousMessages = aiMessages.slice(-MAX_CONVERSATION_MESSAGES);
    const optimisticMessages = [
      ...previousMessages,
      { role: "user", content: normalizedQuery },
    ].slice(-MAX_CONVERSATION_MESSAGES);

    setAiMessages(optimisticMessages);

    try {
      setAiLoading(true);
      setLocationMessage("");

      const needsUserLocation = conversationUsesNearMe(
        normalizedQuery,
        previousMessages
      );

      let userLocation = null;

      if (needsUserLocation) {
        if (savedUserLocation) {
          userLocation = savedUserLocation;
          setLocationMessage("Using your saved location...");
        } else {
          setLocationMessage("Waiting for location permission...");
          userLocation = await getCurrentLocation();
          setSavedUserLocation(userLocation);
          setLocationMessage("Location found. Searching nearby...");
        }
      }

      const data = await searchWithAI(
        normalizedQuery,
        userLocation,
        previousMessages
      );

      const results = Array.isArray(data.results) ? data.results : [];
      const assistantMessage =
        data.assistant_message ||
        data.filters?.explanation ||
        "I searched for matching local businesses.";

      setAiMessages(
        [
          ...optimisticMessages,
          {
            role: "assistant",
            content: assistantMessage,
            results,
            explanation: data.filters?.explanation || "",
            urgency: data.filters?.urgency || "",
            filters: data.filters || {},
          },
        ].slice(-MAX_CONVERSATION_MESSAGES)
      );

      if (needsUserLocation && userLocation && results.length > 0) {
        setLocationMessage("Results are sorted from your current location.");
      } else {
        setLocationMessage("");
      }
    } catch (requestError) {
      console.error("AI search failed:", requestError);

      const failureMessage =
        requestError.message || "AI search is temporarily unavailable.";

      setLocationMessage("");
      setAiMessages(
        [
          ...optimisticMessages,
          {
            role: "assistant",
            content: `Sorry, I couldn't complete that search. ${failureMessage}`,
          },
        ].slice(-MAX_CONVERSATION_MESSAGES)
      );
    } finally {
      setAiLoading(false);
    }
  }

  function handleNewChat() {
    setAiMessages([]);
    setLocationMessage("");
    setSavedUserLocation(null);
  }

  function handlePlaceSelect(place) {
    navigate(`/places/${place.id}`);
  }

  return (
    <main className="app-shell">
      <AISearchBox
        onSearch={handleAISearch}
        onNewChat={handleNewChat}
        onPlaceSelect={handlePlaceSelect}
        messages={aiMessages}
        loading={aiLoading}
        locationMessage={locationMessage}
      />
    </main>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<PlacesPage />} />
      <Route path="/places/:placeId" element={<PlaceDetails />} />
      <Route path="/explore" element={<ExplorePage />} />
      <Route path="/favorites" element={<ProtectedRoute><FavoritesPage /></ProtectedRoute>} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/dashboard/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/dashboard/menu" element={<ProtectedRoute><MenuPage /></ProtectedRoute>} />
      <Route path="/dashboard/reviews" element={<ProtectedRoute><ReviewsPage /></ProtectedRoute>} />
      <Route path="*" element={<PlacesPage />} />
    </Routes>
  );
}

export default App;
