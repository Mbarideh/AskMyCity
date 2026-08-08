# AskMyCity — Final UI & Core Stability Review

This package is the final polish pass before the next product feature.

## Public website
- Reworked the public experience into a local-discovery marketplace rather than a chat/AI clone.
- Added a consistent public header/footer and stronger local-business visual identity.
- Rebuilt the Discover landing page around local intent, categories, amenities and nearby search.
- Kept conversational follow-ups, but presented them as search/refinement turns instead of chat bubbles.
- Removed arbitrary frontend match percentages and misleading AI-looking badges.
- Redesigned Explore, Saved Places, business cards, and business detail pages.
- Business detail pages now surface menu, owner-provided amenities, hours, reviews and exact map location clearly.

## Business workspace
- Simplified navigation to working features only: Overview, Business profile, Menu and Reviews.
- Removed unfinished Gallery/Insights/AI Coach/Claim/Settings routes from the visible product flow.
- Changed the dashboard from an AI-style control panel into a practical business workspace.
- Kept real activity metrics and recent customer activity.
- Reframed rule-based recommendations as a clear next step rather than an AI Coach.
- Added category selection instead of requiring owners to type a category manually.
- Publishing now requires an exact map pin in the frontend.

## Frontend stability
- Added one shared Favorites provider so a page with many cards does not issue a separate favorites request per card.
- Guest Save actions now lead to sign-in instead of silently failing.
- Kept conversational search result IDs so "find more" can avoid duplicates.
- Preserved exact-location behavior and map pinning.
- API URL can now be configured with VITE_API_BASE_URL.

## Backend fixes
- Added the database-only /places/explore endpoint used by the Explore page.
- Kept Business Studio records hidden from Explore until published/active.
- AskMyCity community reviews no longer overwrite imported/public rating and review counts.
- Removed a duplicate Favorite model field.
- Preserved owner-provided amenities separately inside features_json.
- Preserved exact owner-confirmed coordinates for near-me search and directions.

## Validation performed
- Backend Python source compiled successfully with `python -m compileall`.
- Frontend React/JSX module graph parsed successfully with TypeScript's JavaScript parser.
- A full Vite production build could not be executed in the Linux packaging environment because the supplied node_modules contains the Windows-native Rolldown binding. The Windows dependency tree is preserved in this package.

## Local setup note
Keep your own Backend `.env` file when replacing folders. This package intentionally includes `.env.example`, not your private local environment file.
