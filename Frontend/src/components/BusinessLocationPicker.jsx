import { useEffect, useMemo, useState } from "react";
import { divIcon } from "leaflet";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { searchBusinessAddress } from "../services/api";
import "./BusinessLocationPicker.css";

const OTTAWA_CENTER = { latitude: 45.4215, longitude: -75.6972 };

const pinIcon = divIcon({
  className: "askmycity-map-pin-wrap",
  html: '<div class="askmycity-map-pin" aria-hidden="true"><span></span></div>',
  iconSize: [34, 44],
  iconAnchor: [17, 42],
});

function MapController({ location }) {
  const map = useMap();
  useEffect(() => {
    if (!location) return;
    map.flyTo([location.latitude, location.longitude], Math.max(map.getZoom(), 17), { duration: 0.6 });
  }, [location?.latitude, location?.longitude, map]);
  return null;
}

function ClickToPin({ onChange }) {
  useMapEvents({
    click(event) {
      onChange({ latitude: event.latlng.lat, longitude: event.latlng.lng, source: "manual" });
    },
  });
  return null;
}

function DraggablePin({ location, onChange }) {
  const eventHandlers = useMemo(() => ({
    dragend(event) {
      const point = event.target.getLatLng();
      onChange({ latitude: point.lat, longitude: point.lng, source: "manual" });
    },
  }), [onChange]);

  if (!location) return null;
  return (
    <Marker
      position={[location.latitude, location.longitude]}
      draggable
      eventHandlers={eventHandlers}
      icon={pinIcon}
    />
  );
}

export default function BusinessLocationPicker({ token, address, city, postalCode, value, onChange }) {
  const [searching, setSearching] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [results, setResults] = useState([]);
  const [searchText, setSearchText] = useState("");

  useEffect(() => {
    const composed = [address, city, postalCode].filter(Boolean).join(", ");
    setSearchText(composed);
  }, [address, city, postalCode]);

  const center = value || OTTAWA_CENTER;

  async function searchAddress() {
    const query = searchText.trim();
    if (query.length < 4) {
      setLocationError("Enter a complete street address, city, or postal code first.");
      return;
    }
    try {
      setSearching(true);
      setLocationError("");
      const data = await searchBusinessAddress(token, query);
      setResults(Array.isArray(data) ? data : []);
      if (!data?.length) setLocationError("No exact match was found. Use your current location or click the map to place the pin manually.");
    } catch (error) {
      setLocationError(error.message || "Address search failed. You can still place the pin manually.");
    } finally {
      setSearching(false);
    }
  }

  function useCurrentLocation() {
    setLocationError("");
    if (!navigator.geolocation) {
      setLocationError("This browser does not support location access. Click the map to place the pin manually.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onChange({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          source: "gps",
        });
        setResults([]);
      },
      (error) => {
        const message = error.code === 1
          ? "Location permission was denied. Allow location access in the browser, or place the pin manually."
          : "Your current location could not be detected. Place the pin manually instead.";
        setLocationError(message);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
    );
  }

  return (
    <div className="business-location-picker">
      <div className="location-picker-heading">
        <div>
          <h3>Exact map location</h3>
          <p>Search for the address, use your device location, or click/drag the pin. <strong>The pin is the final location AskMyCity saves and uses for “near me”.</strong></p>
        </div>
        {value && <span className="location-confirmed-badge">✓ Pin selected</span>}
      </div>

      <div className="location-search-row">
        <input
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="Example: 833 Richmond Road, Ottawa, ON K2A 0G7"
          aria-label="Search business address"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              searchAddress();
            }
          }}
        />
        <button type="button" className="secondary-action" onClick={searchAddress} disabled={searching}>
          {searching ? "Searching…" : "Find address"}
        </button>
        <button type="button" className="secondary-action location-gps-button" onClick={useCurrentLocation}>
          ◎ Use my current location
        </button>
      </div>

      {results.length > 0 && (
        <div className="location-search-results" role="list" aria-label="Address search results">
          <p className="location-results-label">Choose the correct result — do not accept a nearby neighbourhood if the address is wrong.</p>
          {results.map((result, index) => (
            <button
              type="button"
              role="listitem"
              key={`${result.latitude}-${result.longitude}-${index}`}
              onClick={() => {
                onChange({ latitude: result.latitude, longitude: result.longitude, source: "search" });
                setResults([]);
              }}
            >
              <span>📍</span>
              <span>{result.display_name}</span>
            </button>
          ))}
        </div>
      )}

      {locationError && <p className="location-picker-error">{locationError}</p>}

      <div className="business-map-shell">
        <MapContainer
          center={[center.latitude, center.longitude]}
          zoom={value ? 17 : 12}
          scrollWheelZoom
          className="business-location-map"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapController location={value} />
          <ClickToPin onChange={onChange} />
          <DraggablePin location={value} onChange={onChange} />
        </MapContainer>
        {!value && <div className="map-empty-hint">Click the exact building on the map to place the pin.</div>}
      </div>

      <div className="location-coordinate-row">
        {value ? (
          <>
            <span><strong>Latitude:</strong> {Number(value.latitude).toFixed(6)}</span>
            <span><strong>Longitude:</strong> {Number(value.longitude).toFixed(6)}</span>
            {value.source === "gps" && value.accuracy && <span><strong>GPS accuracy:</strong> about {Math.round(value.accuracy)} m</span>}
            <button type="button" onClick={() => onChange(null)}>Clear pin</button>
          </>
        ) : (
          <span>No exact map pin selected yet.</span>
        )}
      </div>
      <p className="location-picker-note">Address search is only a starting point. If the result lands on the wrong street or neighbourhood, drag the pin to the exact entrance before saving.</p>
    </div>
  );
}
