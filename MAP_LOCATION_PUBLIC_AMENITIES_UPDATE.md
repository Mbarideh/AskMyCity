# AskMyCity update: exact map pin + public amenities

## Business location
- Uses OpenStreetMap/Leaflet in Business Studio.
- Address search returns multiple Canadian candidates instead of silently accepting one guess.
- Address lookup uses Nominatim with Photon/OpenStreetMap fallback.
- Owner can use browser GPS, click the map, or drag the pin.
- The manually confirmed pin is saved through `/dashboard/profile/location` and is the source of truth for near-me search.
- Saving a confirmed pin updates the public Google Maps directions URL to those exact coordinates.

## Public restaurant page
- Reads owner-provided amenities from `places.features_json.owner_provided.data`.
- Shows selected services, parking, seating, accessibility, family options, dietary status, alcohol status, amenities, and payments.
- Unknown/unselected values stay hidden.
