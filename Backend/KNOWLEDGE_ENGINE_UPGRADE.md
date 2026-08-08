# AskMyCity Backend v4.1 — Knowledge Engine

This release adds deterministic concept expansion before candidate verification.

## What changed

- Added `planner/knowledge_engine.py`.
- Normalizes plural and related terms, such as `burgers` → `burger`.
- Matches broad food concepts against dedicated business categories.
- Matches concept families against verified menu evidence.
- Keeps strict evidence rules for specific dishes and dietary claims.
- Preserves the existing API response and frontend integration.

## Evidence policy

A dedicated category can prove a broad concept:

- `Hamburger restaurant` proves `burger`.
- `Pizza restaurant` proves `pizza`.
- `Sushi restaurant` proves `sushi`.

A general category does not prove a specific dish:

- `Italian restaurant` does not prove `gnocchi`.
- `Middle Eastern restaurant` does not prove `shawarma` unless a dedicated category or verified menu supports it.

This prevents both false negatives and hallucinated menu claims.

## Initial concepts

- burger
- pizza
- sushi
- coffee
- shawarma
- ramen

More concepts can be added safely to `CONCEPTS` without changing route logic.
