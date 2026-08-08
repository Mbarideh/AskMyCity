import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({ iconRetinaUrl: markerIcon2x, iconUrl: markerIcon, shadowUrl: markerShadow });

const OTTAWA = [45.4215, -75.6972];

function MoveMap({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.setView(position, 16, { animate: true });
  }, [map, position]);
  return null;
}

function ClickHandler({ onChange }) {
  useMapEvents({
    click(event) {
      onChange({ latitude: event.latlng.lat, longitude: event.latlng.lng });
    },
  });
  return null;
}

export default function BusinessLocationPicker({ location, onChange, onUseAddress, locating }) {
  const position = location ? [Number(location.latitude), Number(location.longitude)] : OTTAWA;
  return (
    <div className="business-location-picker">
      <div className="location-picker-toolbar">
        <div>
          <strong>Confirm your exact location</strong>
          <p>Click the map or drag the pin until it is on your business entrance.</p>
        </div>
        <button type="button" className="secondary-action" onClick={onUseAddress} disabled={locating}>
          {locating ? "Finding address..." : "Find from address"}
        </button>
      </div>
      <MapContainer center={position} zoom={location ? 16 : 11} scrollWheelZoom className="business-location-map">
        <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MoveMap position={location ? position : null} />
        <ClickHandler onChange={onChange} />
        {location && (
          <Marker
            position={position}
            draggable
            eventHandlers={{
              dragend(event) {
                const point = event.target.getLatLng();
                onChange({ latitude: point.lat, longitude: point.lng });
              },
            }}
          />
        )}
      </MapContainer>
      <div className="location-confirmation-row">
        {location ? (
          <span className="location-confirmed">✓ Pin selected: {Number(location.latitude).toFixed(6)}, {Number(location.longitude).toFixed(6)}</span>
        ) : (
          <span className="location-warning">No map location confirmed yet. Use “Find from address,” then adjust the pin.</span>
        )}
      </div>
    </div>
  );
}
