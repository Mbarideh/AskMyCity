import { useEffect, useState } from "react";
import {
  Circle,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "./BusinessMap.css";

import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

/*
  Fix Leaflet's default marker icons when using Vite.
*/
delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const OTTAWA_CENTER = [45.4215, -75.6972];

/*
  Blue circle used for the user's current location.
*/
const userLocationIcon = L.divIcon({
  className: "user-location-marker",
  html: `
    <div class="user-location-dot">
      <div class="user-location-pulse"></div>
    </div>
  `,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

/*
  Automatically fit the map around business markers.
*/
function FitMapToBusinesses({
  businesses,
  userLocation,
}) {
  const map = useMap();

  useEffect(() => {
    /*
      Do not reset the map while the user is viewing
      their current location.
    */
    if (userLocation) {
      return;
    }

    const validBusinesses = businesses.filter(
      (business) =>
        Number.isFinite(Number(business.latitude)) &&
        Number.isFinite(Number(business.longitude))
    );

    if (validBusinesses.length === 0) {
      map.setView(OTTAWA_CENTER, 10);
      return;
    }

    if (validBusinesses.length === 1) {
      map.setView(
        [
          Number(validBusinesses[0].latitude),
          Number(validBusinesses[0].longitude),
        ],
        14
      );

      return;
    }

    const bounds = L.latLngBounds(
      validBusinesses.map((business) => [
        Number(business.latitude),
        Number(business.longitude),
      ])
    );

    map.fitBounds(bounds, {
      padding: [50, 50],
      maxZoom: 14,
    });
  }, [businesses, map, userLocation]);

  return null;
}

/*
  Custom map control for finding the user's location.
*/
function CurrentLocationControl({
  onLocationFound,
  onLocationError,
  locating,
  setLocating,
}) {
  const map = useMap();

  function findCurrentLocation() {
    if (!navigator.geolocation) {
      onLocationError(
        "Your browser does not support location services."
      );

      return;
    }

    setLocating(true);
    onLocationError("");

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        };

        onLocationFound(location);

        map.flyTo(
          [location.latitude, location.longitude],
          15,
          {
            duration: 1.2,
          }
        );

        setLocating(false);
      },
      (error) => {
        let message =
          "We could not determine your location.";

        if (error.code === error.PERMISSION_DENIED) {
          message =
            "Location permission was denied. Please allow location access in your browser.";
        } else if (
          error.code === error.POSITION_UNAVAILABLE
        ) {
          message =
            "Your current location is unavailable.";
        } else if (error.code === error.TIMEOUT) {
          message =
            "Finding your location took too long. Please try again.";
        }

        onLocationError(message);
        setLocating(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 12000,
        maximumAge: 60000,
      }
    );
  }

  return (
    <div className="location-control">
      <button
        type="button"
        className="location-button"
        onClick={findCurrentLocation}
        disabled={locating}
        title="Show my current location"
        aria-label="Show my current location"
      >
        {locating ? (
          <span className="location-spinner" />
        ) : (
          <span className="location-symbol">◎</span>
        )}
      </button>
    </div>
  );
}

export default function BusinessMap({
  businesses = [],
  onBusinessSelect,
}) {
  const [userLocation, setUserLocation] =
    useState(null);

  const [locationError, setLocationError] =
    useState("");

  const [locating, setLocating] =
    useState(false);

  const validBusinesses = businesses.filter(
    (business) =>
      Number.isFinite(Number(business.latitude)) &&
      Number.isFinite(Number(business.longitude))
  );

  return (
    <div className="business-map-wrapper">
      {locationError && (
        <div className="location-error">
          <span>{locationError}</span>

          <button
            type="button"
            onClick={() => setLocationError("")}
            aria-label="Close location message"
          >
            ×
          </button>
        </div>
      )}

      <MapContainer
        center={OTTAWA_CENTER}
        zoom={10}
        scrollWheelZoom
        zoomControl
        className="business-map"
      >
        {/*
          CARTO Voyager gives the map a cleaner,
          more modern visual style.
        */}
        <TileLayer
          attribution='&copy; OpenStreetMap contributors &copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />

        <FitMapToBusinesses
          businesses={validBusinesses}
          userLocation={userLocation}
        />

        <CurrentLocationControl
          onLocationFound={setUserLocation}
          onLocationError={setLocationError}
          locating={locating}
          setLocating={setLocating}
        />

        {userLocation && (
          <>
            <Circle
              center={[
                userLocation.latitude,
                userLocation.longitude,
              ]}
              radius={userLocation.accuracy}
              pathOptions={{
                color: "#2563eb",
                fillColor: "#60a5fa",
                fillOpacity: 0.15,
                weight: 1,
              }}
            />

            <Marker
              position={[
                userLocation.latitude,
                userLocation.longitude,
              ]}
              icon={userLocationIcon}
              zIndexOffset={1000}
            >
              <Popup>
                <div className="map-popup">
                  <h3>Your location</h3>

                  <p>
                    Accuracy: approximately{" "}
                    {Math.round(
                      userLocation.accuracy
                    )}{" "}
                    metres
                  </p>
                </div>
              </Popup>
            </Marker>
          </>
        )}

        {validBusinesses.map((business) => (
          <Marker
            key={business.id}
            position={[
              Number(business.latitude),
              Number(business.longitude),
            ]}
          >
            <Popup>
              <div className="map-popup">
                <h3>{business.name}</h3>

                <p className="map-popup-category">
                  {business.category ||
                    "Local business"}
                </p>

                <p>
                  ⭐{" "}
                  {business.rating !== null &&
                  business.rating !== undefined
                    ? business.rating
                    : "Not rated"}
                </p>

                <p>
                  📍{" "}
                  {business.city ||
                    "Location unavailable"}
                </p>

                <button
                  type="button"
                  className="map-popup-button"
                  onClick={() =>
                    onBusinessSelect?.(business)
                  }
                >
                  View business
                </button>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}