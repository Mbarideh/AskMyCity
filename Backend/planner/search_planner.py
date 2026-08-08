from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchPlan:
    """Deterministic execution plan built from the AI-extracted filters.

    The language model understands the request. This class decides how the
    backend executes it, so radius expansion and stopping rules stay
    predictable, testable, and inexpensive.
    """

    hard_requirements: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    radius_steps_km: list[float] = field(default_factory=lambda: [5.0, 10.0, 20.0])
    minimum_results: int = 3
    maximum_results: int = 10
    ranking_mode: str = "balanced"
    expansion_reason: str = "not_enough_verified_results"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def build_search_plan(user_query: str, filters: Any, uses_location: bool) -> SearchPlan:
    """Create a deterministic search plan from extracted intent.

    ``filters`` intentionally accepts any object with attributes so this module
    does not depend on FastAPI or SQLModel and can be unit-tested separately.
    """

    text = user_query.strip().lower()
    hard: list[str] = []
    preferences: list[str] = []

    if getattr(filters, "category", None):
        hard.append(f"category:{filters.category}")
    if getattr(filters, "requested_cuisine", None):
        hard.append(f"cuisine:{filters.requested_cuisine}")
    for dish in getattr(filters, "requested_dishes", []) or []:
        hard.append(f"dish:{dish}")
    for option in getattr(filters, "dietary_options", []) or []:
        hard.append(f"dietary:{option}")
    if getattr(filters, "open_now", None) is True:
        hard.append("open_now")
    if getattr(filters, "maximum_price", None) is not None:
        hard.append(f"maximum_price:{filters.maximum_price:g}")
    if getattr(filters, "minimum_rating", None) is not None:
        hard.append(f"minimum_rating:{filters.minimum_rating:g}")
    if getattr(filters, "minimum_review_count", None) is not None:
        hard.append(f"minimum_reviews:{filters.minimum_review_count}")

    asks_closest = _contains(text, [r"\bclosest\b", r"\bnearest\b", r"\bvery close\b"])
    asks_best = _contains(text, [r"\bbest\b", r"\btop[- ]rated\b", r"\bhighest[- ]rated\b", r"\bhighly rated\b"])
    asks_cheap = _contains(text, [r"\bcheap\b", r"\baffordable\b", r"\bbudget\b", r"\binexpensive\b"])

    if uses_location:
        preferences.append("nearby")
    if asks_closest:
        preferences.insert(0, "closest")
    if asks_best or getattr(filters, "minimum_rating", None) is not None:
        preferences.append("high_rating")
    if asks_cheap or getattr(filters, "budget_preference", None) == "affordable":
        preferences.append("affordable")
    if getattr(filters, "minimum_review_count", None) is not None:
        preferences.append("well_reviewed")
    preferences.append("strong_evidence")

    if not uses_location:
        radius_steps = []
        ranking_mode = "quality"
    elif asks_closest:
        radius_steps = [3.0, 5.0, 8.0, 12.0]
        ranking_mode = "distance"
    elif asks_best:
        radius_steps = [5.0, 10.0, 20.0, 30.0]
        ranking_mode = "quality"
    elif getattr(filters, "open_now", None) is True or getattr(filters, "dietary_options", None):
        radius_steps = [5.0, 10.0, 20.0, 25.0]
        ranking_mode = "balanced"
    else:
        radius_steps = [3.0, 5.0, 10.0, 20.0]
        ranking_mode = "balanced"

    # One excellent exact-name result is enough. General discovery should aim
    # for three choices so the concierge can compare options.
    minimum_results = 1 if getattr(filters, "search", None) and not (
        getattr(filters, "requested_dishes", None)
        or getattr(filters, "dietary_options", None)
    ) else 3

    return SearchPlan(
        hard_requirements=hard,
        preferences=list(dict.fromkeys(preferences)),
        radius_steps_km=radius_steps,
        minimum_results=minimum_results,
        maximum_results=10,
        ranking_mode=ranking_mode,
    )
