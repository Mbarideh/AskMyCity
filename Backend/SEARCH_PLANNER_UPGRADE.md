# AskMyCity Search Planner Upgrade (v2.4)

## Added

- Deterministic intent-aware search plans.
- Hard requirements vs. ranking preferences.
- Expanding-radius search for GPS/near-me requests.
- Different radius policies for closest, best, open-now, and dietary searches.
- Evidence-sensitive stopping rules.
- Search-plan metadata returned by `/ai/search`.

## New package

- `planner/search_planner.py`
- `planner/radius_engine.py`
- `planner/evidence_engine.py`

## API compatibility

The existing `/ai/search` request body is unchanged. The response now includes
an optional `search_plan` object. Existing frontends can ignore it.

## Example response metadata

```json
{
  "search_plan": {
    "hard_requirements": ["category:restaurant", "dietary:halal"],
    "preferences": ["nearby", "high_rating", "strong_evidence"],
    "radius_steps_km": [5, 10, 20, 25],
    "minimum_results": 3,
    "maximum_results": 10,
    "ranking_mode": "balanced",
    "radius_used_km": 10,
    "radius_expanded": true
  }
}
```
