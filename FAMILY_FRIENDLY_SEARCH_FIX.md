# AskMyCity family-friendly / amenity search fix

This release fixes a regression where queries such as:

- Find family-friendly restaurants near me
- Italian restaurants with parking
- Restaurants with a patio near me

could return zero results even when the saved database already contained matching amenity data.

## Root cause
The AI planner could classify `family-friendly` as a dietary or generic atmosphere term. The strict dietary gate then required dietary evidence for it, which is incorrect. In addition, owner-provided `features_json` and imported `service_features_json` were not part of the hard amenity filter path.

## Fix
- Added deterministic amenity/service intent detection.
- Added `requested_features` to search filters.
- Family-friendly, parking, patio, dine-in, takeout, delivery, reservations, Wi-Fi, kids menu, high chairs, and accessibility are treated as amenities/services, not dietary restrictions.
- Requested amenities are hard constraints: unrelated highly rated restaurants cannot be used as substitutes.
- First-party Business Studio amenity selections in `Place.features_json.owner_provided.data` are used as direct saved evidence.
- Imported/enriched `BusinessAIProfile.service_features_json` is also used.
- Amenity constraints are preserved for `Find N more` follow-ups.
- Near-me amenity searches stay PostgreSQL-first and do not trigger live enrichment/API calls.
- Added saved features/service features to the combined business knowledge text.

Backend Python files compile successfully.
