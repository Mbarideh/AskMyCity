import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from math import (
    atan2,
    cos,
    radians,
    sin,
    sqrt,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import func, or_
from sqlmodel import Session, select

from ai_service import understand_search_query
from ai_enrichment_service import PROMPT_VERSION, enrich_place
from database import get_session
from models import BusinessAIProfile, BusinessResearchCache, Place
from schemas import (
    AISearchFilters,
    AISearchRequest,
    AISearchResponse,
    PlaceResult,
)


router = APIRouter(
    prefix="/ai",
    tags=["AI Search"],
)


RESEARCH_BATCH_SIZE = max(1, min(2, int(os.getenv("AI_RESEARCH_BATCH_SIZE", "1"))))
RESEARCH_MAX_CANDIDATES = max(1, min(20, int(os.getenv("AI_RESEARCH_MAX_CANDIDATES", "12"))))
RESEARCH_TARGET_RESULTS = max(1, min(2, int(os.getenv("AI_RESEARCH_TARGET_RESULTS", "1"))))

# Progressive "near me" search policy.
# Near-me searches use SAVED PostgreSQL knowledge only.
PROGRESSIVE_RADII_KM = (0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0)
PROGRESSIVE_TARGET_RESULTS = max(
    1, min(10, int(os.getenv("PROGRESSIVE_TARGET_RESULTS", "5")))
)
PROGRESSIVE_DISPLAY_LIMIT = max(
    PROGRESSIVE_TARGET_RESULTS,
    min(10, int(os.getenv("PROGRESSIVE_DISPLAY_LIMIT", "5"))),
)
DISH_CUISINE_HINTS = {
    "gnocchi": "Italian",
    "carbonara": "Italian",
    "ravioli": "Italian",
    "lasagna": "Italian",
    "tiramisu": "Italian",
    "pasta": "Italian",
    "penne": "Italian",
    "spaghetti": "Italian",
    "fettuccine": "Italian",
    "linguine": "Italian",
    "rigatoni": "Italian",
    "tagliatelle": "Italian",
    "tortellini": "Italian",
    "ramen": "Japanese",
    "sushi": "Japanese",
    "koobideh": "Persian",
}


DIETARY_QUERY_ALIASES = {
    "halal": {
        "halal", "halaal", "hallal", "hall", "halel", "helal",
    },
    "kosher": {"kosher", "kasher"},
    "vegan": {"vegan"},
    "vegetarian": {"vegetarian", "veggie"},
    "gluten free": {"glutenfree", "gluten-free", "gluten free"},
}

# Deterministic business-feature intent. These are not dietary requirements.
# They must be satisfied from saved PostgreSQL knowledge (owner-provided
# amenities, imported/enriched service features, or explicit saved features).
FEATURE_QUERY_ALIASES = {
    "family_friendly": {"family friendly", "family-friendly", "good for families", "kid friendly", "kid-friendly"},
    "kids_menu": {"kids menu", "kid menu", "children's menu", "childrens menu"},
    "high_chairs": {"high chairs", "high chair"},
    "parking": {"parking", "parking available"},
    "free_parking": {"free parking"},
    "paid_parking": {"paid parking"},
    "street_parking": {"street parking"},
    "patio": {"patio", "outdoor seating", "terrace"},
    "dine_in": {"dine in", "dine-in", "dining in"},
    "takeout": {"takeout", "take out", "take-out"},
    "delivery": {"delivery", "delivers"},
    "reservations": {"reservation", "reservations", "book a table"},
    "wifi": {"wifi", "wi-fi", "wireless internet"},
    "wheelchair_accessible": {"wheelchair accessible", "wheelchair-accessible", "accessible entrance"},
}

FEATURE_DISPLAY_NAMES = {
    "family_friendly": "family-friendly",
    "kids_menu": "kids menu",
    "high_chairs": "high chairs",
    "parking": "parking",
    "free_parking": "free parking",
    "paid_parking": "paid parking",
    "street_parking": "street parking",
    "patio": "patio",
    "dine_in": "dine-in",
    "takeout": "takeout",
    "delivery": "delivery",
    "reservations": "reservations",
    "wifi": "Wi-Fi",
    "wheelchair_accessible": "wheelchair accessibility",
}


def _normalize_feature_value(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def infer_requested_features_from_query(query: str) -> list[str]:
    raw = str(query or "").strip().lower()
    if not raw:
        return []
    normalized = re.sub(r"[^a-z0-9]+", " ", raw)
    found: list[str] = []
    # Match more specific parking phrases before generic parking.
    ordered = sorted(
        FEATURE_QUERY_ALIASES.items(),
        key=lambda item: max(len(alias) for alias in item[1]),
        reverse=True,
    )
    for canonical, aliases in ordered:
        if any(re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip() in normalized for alias in aliases):
            found.append(canonical)
    specific_parking = {"free_parking", "paid_parking", "street_parking"}
    if specific_parking.intersection(found):
        found = [item for item in found if item != "parking"]
    return list(dict.fromkeys(found))


def _feature_alias_normalized_values(feature: str) -> set[str]:
    canonical = _normalize_feature_value(feature)
    aliases = FEATURE_QUERY_ALIASES.get(canonical, {feature})
    values = {canonical}
    values.update(_normalize_feature_value(alias) for alias in aliases)
    if canonical == "wheelchair_accessible":
        values.update({"wheelchair_entrance", "wheelchair_seating", "wheelchair_washroom"})
    return {value for value in values if value}


def infer_dietary_options_from_query(query: str) -> list[str]:
    """Deterministic safety net for dietary intent, including common typos.

    The AI planner remains primary, but a hard dietary condition must not be
    silently dropped just because the user misspells one word (for example,
    `hall resurant near me` when they clearly mean `halal restaurant near me`).
    """
    raw = str(query or "").strip().lower()
    if not raw:
        return []

    compact = re.sub(r"[^a-z0-9]+", " ", raw)
    tokens = set(compact.split())
    restaurant_context = any(
        token in tokens
        for token in {"restaurant", "restaurants", "resturant", "resurant", "restraunt", "food", "eatery"}
    )

    found: list[str] = []
    for canonical, aliases in DIETARY_QUERY_ALIASES.items():
        matched = False
        for alias in aliases:
            alias_normalized = alias.replace("-", " ")
            if " " in alias_normalized:
                if alias_normalized in compact:
                    matched = True
                    break
            elif alias_normalized in tokens:
                # `hall` is ambiguous by itself. Only treat it as the common
                # misspelling of halal when the request is clearly for food/
                # restaurants. This prevents "banquet hall near me" from being
                # converted into a halal request.
                if alias_normalized == "hall" and not restaurant_context:
                    continue
                matched = True
                break
        if matched:
            found.append(canonical)
    return found


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _merge_json_lists(existing_json: str | None, new_values, key_name: str | None = None) -> str:
    try:
        existing = json.loads(existing_json or "[]")
    except (TypeError, json.JSONDecodeError):
        existing = []
    incoming = new_values if isinstance(new_values, list) else []
    merged = []
    seen = set()
    for item in [*existing, *incoming]:
        if key_name and isinstance(item, dict):
            identity = str(item.get(key_name, "")).strip().lower()
        else:
            identity = json.dumps(item, sort_keys=True, ensure_ascii=False).lower()
        if identity and identity not in seen:
            merged.append(item)
            seen.add(identity)
    return _json_dump(merged)


def save_enrichment_profile(session: Session, place: Place, data: dict) -> None:
    """Merge targeted AI research without touching the raw imported place."""
    profile = session.exec(
        select(BusinessAIProfile).where(BusinessAIProfile.place_id == place.id)
    ).first()
    if profile is None:
        profile = BusinessAIProfile(place_id=place.id)

    profile.ai_summary = data.get("ai_summary") or profile.ai_summary
    profile.cuisine_types_json = _merge_json_lists(profile.cuisine_types_json, data.get("cuisine_types", []))
    profile.cuisine_confidence = data.get("cuisine_confidence", "low")
    profile.menu_items_json = _merge_json_lists(profile.menu_items_json, data.get("menu_items", []))
    profile.menu_confidence = data.get("menu_confidence", "low")
    profile.signature_items_json = _merge_json_lists(profile.signature_items_json, data.get("signature_items", []))
    profile.dish_reputation_json = _merge_json_lists(profile.dish_reputation_json, data.get("dish_reputation", []), key_name="item")
    profile.price_level = data.get("price_level")
    profile.average_main_price_cad = data.get("average_main_price_cad")
    profile.price_confidence = data.get("price_confidence", "low")
    profile.value_for_money = data.get("value_for_money")
    profile.best_for_json = _merge_json_lists(profile.best_for_json, data.get("best_for", []))
    profile.atmosphere_json = _merge_json_lists(profile.atmosphere_json, data.get("atmosphere", []))
    profile.dietary_options_json = _merge_json_lists(profile.dietary_options_json, data.get("dietary_options", []))
    profile.service_features_json = _merge_json_lists(profile.service_features_json, data.get("service_features", []))
    profile.search_tags_json = _merge_json_lists(profile.search_tags_json, data.get("search_tags", []))
    profile.evidence_summary = data.get("evidence_summary")
    profile.confidence = data.get("confidence", "low")
    profile.source_urls_json = _merge_json_lists(profile.source_urls_json, data.get("source_urls", []))
    profile.enrichment_mode = data.get("enrichment_mode", "web")
    profile.model_name = data.get("model_name")
    profile.prompt_version = data.get("prompt_version", PROMPT_VERSION)
    profile.updated_at = utc_now()
    session.add(profile)

CITY_ALIASES = {
    "napeen": "Nepean",
    "nepeen": "Nepean",
    "neapen": "Nepean",
    "nepean": "Nepean",
    "ottowa": "Ottawa",
    "ottawa": "Ottawa",
    "orleans": "Orléans",
    "orlean": "Orléans",
    "orléans": "Orléans",
    "kanata": "Kanata",
    "gatineau": "Gatineau",
    "barrhaven": "Barrhaven",
    "stittsville": "Stittsville",
}


def normalize_city(
    city: str | None,
) -> str | None:
    """
    Clean a city name and correct known spelling
    variations.
    """

    if not city:
        return None

    cleaned_city = city.strip()

    if not cleaned_city:
        return None

    normalized_key = cleaned_city.lower()

    return CITY_ALIASES.get(
        normalized_key,
        cleaned_city,
    )


def normalize_minimum_rating(
    value,
) -> float | None:
    """
    Convert the requested minimum rating into a
    number between zero and five.
    """

    if value is None:
        return None

    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None

    return max(
        0,
        min(5, rating),
    )


def normalize_minimum_review_count(
    value,
) -> int | None:
    """
    Convert the requested minimum review count into
    a non-negative integer.
    """

    if value is None:
        return None

    try:
        review_count = int(value)
    except (TypeError, ValueError):
        return None

    return max(0, review_count)


def query_uses_near_me(
    user_query: str,
) -> bool:
    """
    Detect near-me phrases in the latest query.
    """

    normalized_query = user_query.lower().strip()

    near_me_patterns = [
        r"\bnear\s+me\b",
        r"\bnearby\b",
        r"\bclose\s+to\s+me\b",
        r"\bclosest\s+to\s+me\b",
        r"\baround\s+me\b",
        r"\bin\s+my\s+area\b",
    ]

    return any(
        re.search(
            pattern,
            normalized_query,
        )
        for pattern in near_me_patterns
    )


def conversation_uses_near_me(
    request: AISearchRequest,
) -> bool:
    """
    Detect whether the latest request or recent
    conversation refers to the user's location.

    This allows follow-up requests such as:
        Find a plumber near me
        Only show highly rated ones

    The second message still uses the saved GPS
    coordinates even though it does not contain
    the words "near me".
    """

    if query_uses_near_me(
        request.query
    ):
        return True

    for message in request.messages:
        if (
            message.role == "user"
            and query_uses_near_me(
                message.content
            )
        ):
            return True

    return False



MORE_WORDS = {
    "more", "another", "additional", "next", "others", "other"
}


def query_requests_more(user_query: str) -> bool:
    """Return True for conversational pagination such as 'find 2 more'."""
    normalized = user_query.lower().strip()
    return any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in MORE_WORDS)


def requested_more_count(user_query: str, default: int = 5) -> int:
    """Extract how many additional results the user asked for."""
    normalized = user_query.lower().strip()
    number_match = re.search(r"\b(\d{1,2})\b", normalized)
    if number_match:
        return max(1, min(10, int(number_match.group(1))))

    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    for word, value in words.items():
        if re.search(rf"\b{word}\b", normalized):
            return value
    return default


def previous_displayed_count(messages) -> int:
    """Infer how many cards were shown in the immediately previous answer.

    The frontend currently sends conversation text rather than result IDs.  We
    therefore derive the offset from the last assistant summary, e.g.
    'I found 2 ... within 1 km. I also found 4 additional ...' => 6.
    """
    for message in reversed(messages or []):
        if getattr(message, "role", None) != "assistant":
            continue
        content = str(getattr(message, "content", "") or "")
        primary = re.search(r"\bI found\s+(\d+)\b", content, re.I)
        additional = re.search(r"\bI also found\s+(\d+)\s+additional\b", content, re.I)
        if primary:
            count = int(primary.group(1))
            if additional:
                count += int(additional.group(1))
            return count
    return 0


def previously_displayed_result_ids(messages) -> list[int]:
    """Return unique result IDs from all prior assistant turns, in display order."""
    seen: set[int] = set()
    ordered: list[int] = []
    for message in messages or []:
        if getattr(message, "role", None) != "assistant":
            continue
        for raw_id in getattr(message, "result_ids", None) or []:
            try:
                result_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if result_id > 0 and result_id not in seen:
                seen.add(result_id)
                ordered.append(result_id)
    return ordered


def query_asks_closest_from_previous(user_query: str) -> bool:
    """Detect contextual questions such as 'which one is the closest?'"""
    normalized = user_query.lower().strip()
    patterns = (
        r"\bwhich\s+(?:one|ones)\s+is\s+(?:the\s+)?closest\b",
        r"\bwhich\s+is\s+(?:the\s+)?closest\b",
        r"\bclosest\s+(?:one|option|restaurant|place)\b",
        r"\bnearest\s+(?:one|option|restaurant|place)\b",
        r"\bwhich\s+(?:one|ones)\s+is\s+(?:the\s+)?nearest\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def results_for_exact_ids(
    session: Session,
    ids: list[int],
    filters: AISearchFilters,
    user_latitude: float | None,
    user_longitude: float | None,
) -> list[PlaceResult]:
    """Load exactly the previously displayed places and preserve their order."""
    if not ids:
        return []
    rows = session.exec(select(Place).where(Place.id.in_(ids))).all()
    by_id = {place.id: place for place in rows if place.id is not None}
    ordered_places = [by_id[result_id] for result_id in ids if result_id in by_id]
    # Do not re-apply the newest natural-language search text (for example the
    # word "closest") as a business keyword.  These IDs are already the user's
    # accepted conversational result set; this step only compares them.
    context_filters = copy_search_filters(
        filters,
        search=None,
        requested_cuisine=None,
        requested_dishes=[],
        dietary_options=[],
        minimum_rating=None,
        minimum_review_count=None,
    )
    return rank_candidates(
        session,
        ordered_places,
        context_filters,
        user_latitude=user_latitude,
        user_longitude=user_longitude,
    )


def inherit_dietary_from_history_if_needed(filters: AISearchFilters, request: AISearchRequest) -> None:
    """Safety fallback for terse follow-ups like 'find 2 more'."""
    if filters.dietary_options or not query_requests_more(request.query):
        return
    for message in reversed(request.messages or []):
        if getattr(message, "role", None) != "user":
            continue
        options = infer_dietary_options_from_query(str(getattr(message, "content", "") or ""))
        if options:
            filters.dietary_options = list(options)
            return


def inherit_features_from_history_if_needed(filters: AISearchFilters, request: AISearchRequest) -> None:
    """Preserve hard amenity/service constraints on terse follow-ups."""
    if filters.requested_features or not query_requests_more(request.query):
        return
    for message in reversed(request.messages or []):
        if getattr(message, "role", None) != "user":
            continue
        features = infer_requested_features_from_query(str(getattr(message, "content", "") or ""))
        if features:
            filters.requested_features = list(features)
            return


def calculate_distance_km(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Calculate the straight-line distance between
    two GPS coordinates with the Haversine formula.
    """

    earth_radius_km = 6371.0

    latitude_difference = radians(
        latitude_2 - latitude_1
    )

    longitude_difference = radians(
        longitude_2 - longitude_1
    )

    first_latitude = radians(
        latitude_1
    )

    second_latitude = radians(
        latitude_2
    )

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(first_latitude)
        * cos(second_latitude)
        * sin(longitude_difference / 2) ** 2
    )

    angular_distance = 2 * atan2(
        sqrt(haversine_value),
        sqrt(1 - haversine_value),
    )

    return (
        earth_radius_km
        * angular_distance
    )


def build_place_query(
    filters: AISearchFilters,
    include_city: bool = True,
    result_limit: int = 10,
):
    """
    Build a database query from the filters
    extracted by the AI.
    """

    statement = select(Place).outerjoin(
        BusinessAIProfile,
        BusinessAIProfile.place_id == Place.id,
    )

    if filters.category:
        normalized_category = filters.category.strip().lower()
        category_values = {
            normalized_category,
            normalized_category.rstrip("s"),
            f"{normalized_category.rstrip('s')}s",
        }

        category_conditions = []

        for category_value in category_values:
            if not category_value:
                continue

            category_pattern = f"%{category_value}%"
            category_conditions.extend(
                [
                    Place.category.ilike(category_pattern),
                    Place.business_type.ilike(category_pattern),
                    Place.subtypes.ilike(category_pattern),
                ]
            )

        statement = statement.where(
            or_(*category_conditions)
        )

    if include_city and filters.city:
        city_value = (
            f"%{filters.city.strip()}%"
        )

        statement = statement.where(
            or_(
                Place.city.ilike(
                    city_value
                ),
                Place.full_address.ilike(
                    city_value
                ),
            )
        )

    if filters.search:
        search_value = (
            f"%{filters.search.strip()}%"
        )

        statement = statement.where(
            or_(
                Place.name.ilike(
                    search_value
                ),
                Place.category.ilike(
                    search_value
                ),
                Place.business_type.ilike(
                    search_value
                ),
                Place.subtypes.ilike(
                    search_value
                ),
                Place.price_range.ilike(
                    search_value
                ),
                Place.description.ilike(
                    search_value
                ),
                Place.full_address.ilike(
                    search_value
                ),
                Place.city.ilike(
                    search_value
                ),
                BusinessAIProfile.ai_summary.ilike(
                    search_value
                ),
                BusinessAIProfile.cuisine_types_json.ilike(
                    search_value
                ),
                BusinessAIProfile.signature_items_json.ilike(
                    search_value
                ),
                BusinessAIProfile.best_for_json.ilike(
                    search_value
                ),
                BusinessAIProfile.atmosphere_json.ilike(
                    search_value
                ),
                BusinessAIProfile.dietary_options_json.ilike(
                    search_value
                ),
                BusinessAIProfile.service_features_json.ilike(
                    search_value
                ),
                BusinessAIProfile.search_tags_json.ilike(
                    search_value
                ),
            )
        )

    if (
        filters.minimum_rating
        is not None
    ):
        statement = statement.where(
            Place.rating
            >= filters.minimum_rating
        )

    if (
        filters.minimum_review_count
        is not None
    ):
        statement = statement.where(
            Place.review_count
            >= filters.minimum_review_count
        )

    return statement.order_by(
        Place.rating.desc().nullslast(),
        Place.review_count.desc().nullslast(),
    ).limit(result_limit)



def build_keyword_fallbacks(
    search: str | None,
) -> list[str]:
    """Return narrower searchable keywords without dropping the whole intent.

    Example: ``Italian pasta`` becomes ``Italian`` and ``pasta``.  This lets
    the database preserve a cuisine match even when a dish has not yet been
    enriched.
    """

    if not search:
        return []

    cleaned = re.sub(r"[^\wÀ-ÿ'-]+", " ", search).strip()
    if not cleaned:
        return []

    words = [word for word in cleaned.split() if len(word) > 2]
    ignored_words = {
        "with", "and", "the", "good", "best", "cheap", "affordable",
        "restaurant", "restaurants", "place", "places", "near", "open",
    }
    words = [word for word in words if word.lower() not in ignored_words]

    # Cuisine words are generally more reliable database filters than dish
    # names, so test them first when they are present.
    cuisine_words = {
        "italian", "french", "indian", "persian", "iranian", "chinese",
        "japanese", "korean", "thai", "vietnamese", "mexican", "greek",
        "lebanese", "turkish", "mediterranean", "ethiopian", "caribbean",
        "american", "canadian", "afghan", "pakistani", "moroccan",
    }

    ordered = sorted(
        words,
        key=lambda word: (word.lower() not in cuisine_words, words.index(word)),
    )

    unique: list[str] = []
    for word in ordered:
        if word.lower() not in {item.lower() for item in unique}:
            unique.append(word)

    return unique

def copy_search_filters(
    filters: AISearchFilters,
    *,
    search: str | None | object = ...,
    requested_cuisine: str | None | object = ...,
    requested_dishes: list[str] | object = ...,
    dietary_options: list[str] | object = ...,
    requested_features: list[str] | object = ...,
    maximum_price: float | None | object = ...,
    minimum_rating: float | None | object = ...,
    minimum_review_count: int | None | object = ...,
) -> AISearchFilters:
    """Create a modified copy without relying on a Pydantic version."""

    return AISearchFilters(
        category=filters.category,
        city=filters.city,
        search=(
            filters.search
            if search is ...
            else search
        ),
        requested_cuisine=(
            filters.requested_cuisine
            if requested_cuisine is ...
            else requested_cuisine
        ),
        requested_dishes=(
            list(filters.requested_dishes)
            if requested_dishes is ...
            else list(requested_dishes or [])
        ),
        budget_preference=filters.budget_preference,
        maximum_price=(
            filters.maximum_price
            if maximum_price is ...
            else maximum_price
        ),
        atmosphere=list(filters.atmosphere),
        dietary_options=(
            list(filters.dietary_options)
            if dietary_options is ...
            else list(dietary_options or [])
        ),
        requested_features=(
            list(filters.requested_features)
            if requested_features is ...
            else list(requested_features or [])
        ),
        open_now=filters.open_now,
        language=filters.language,
        context_mode=filters.context_mode,
        minimum_rating=(
            filters.minimum_rating
            if minimum_rating is ...
            else minimum_rating
        ),
        minimum_review_count=(
            filters.minimum_review_count
            if minimum_review_count is ...
            else minimum_review_count
        ),
        urgency=filters.urgency,
        explanation=filters.explanation,
    )


def run_place_query(
    session: Session,
    filters: AISearchFilters,
    *,
    include_city: bool,
    result_limit: int = 100,
) -> list[Place]:
    """Execute one candidate search and return its places."""

    statement = build_place_query(
        filters=filters,
        include_city=include_city,
        result_limit=result_limit,
    )

    return list(
        session.exec(statement).all()
    )


def build_relaxed_result_message(
    *,
    result_count: int,
    category: str | None,
    city: str | None,
    removed_keyword: str | None,
    removed_quality_filters: bool,
    widened_area: bool,
) -> str:
    """Explain an honest closest-match fallback to the user."""

    business_name = category or "business"
    location_text = f" in {city}" if city and not widened_area else ""

    if removed_keyword:
        intro = (
            f"I couldn't reliably verify “{removed_keyword}” from the "
            "information currently stored"
        )
    elif removed_quality_filters:
        intro = (
            "I couldn't find enough options that met every rating "
            "or review requirement"
        )
    elif widened_area:
        intro = (
            f"I couldn't find suitable options in {city}"
            if city
            else "I widened the search area"
        )
    else:
        intro = "I found the closest available options"

    count_text = (
        f"Here is the closest {business_name} option{location_text}."
        if result_count == 1
        else (
            f"Here are {result_count} of the best available "
            f"{business_name} options{location_text}."
        )
    )

    return f"{intro}. {count_text}"



CUISINE_KEYWORDS = {
    "italian", "french", "indian", "persian", "iranian", "chinese",
    "japanese", "korean", "thai", "vietnamese", "mexican", "greek",
    "lebanese", "turkish", "mediterranean", "ethiopian", "caribbean",
    "american", "canadian", "afghan", "pakistani", "moroccan", "spanish",
}

CUISINE_ALIASES = {
    "persian": {"persian", "iranian", "iran"},
    "iranian": {"persian", "iranian", "iran"},
    "italian": {"italian", "italy"},
    "middle eastern": {"middle eastern", "mediterranean", "levantine"},
}

def cuisine_terms(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = value.strip().lower()
    return CUISINE_ALIASES.get(normalized, {normalized})

DISH_KEYWORDS = {
    "pasta", "penne", "spaghetti", "fettuccine", "linguine",
    "rigatoni", "tagliatelle", "tortellini", "ravioli", "gnocchi",
    "carbonara", "lasagna", "pizza", "burger", "sushi", "ramen", "steak", "tacos",
    "falafel", "shawarma", "kebab", "curry", "noodles", "sandwich",
    "seafood", "breakfast", "brunch", "dessert", "coffee",
}

NON_RESTAURANT_TERMS = {
    "grocery", "grocer", "supermarket", "convenience", "food shop",
    "food store", "market", "wholesale", "catering", "caterer",
    "interiors", "blinds", "auto", "pharmacy", "bakery supplier",
}


def extract_request_preferences(user_query: str, search: str | None) -> tuple[str | None, list[str], str | None]:
    normalized = f"{user_query} {search or ''}".lower()
    cuisine = next((item.title() for item in CUISINE_KEYWORDS if re.search(rf"\b{re.escape(item)}\b", normalized)), None)
    dishes = sorted({item for item in DISH_KEYWORDS if re.search(rf"\b{re.escape(item)}\b", normalized)})
    budget = None
    if re.search(r"\b(cheap|inexpensive|affordable|budget|low[- ]cost)\b", normalized):
        budget = "affordable"
    elif re.search(r"\b(luxury|fine dining|expensive|upscale)\b", normalized):
        budget = "upscale"
    return cuisine, dishes, budget


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [value]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item is not None]
    if isinstance(parsed, dict):
        return [str(item) for item in parsed.values() if item is not None]
    return [str(parsed)]


def combined_business_text(place: Place, profile: BusinessAIProfile | None = None) -> str:
    parts = [
        place.name, place.category, place.business_type, place.subtypes,
        place.description, place.price_range, place.features_json,
    ]
    if profile:
        parts.extend([
            profile.ai_summary, profile.cuisine_types_json,
            profile.menu_items_json, profile.signature_items_json,
            profile.dish_reputation_json, profile.search_tags_json,
            profile.best_for_json, profile.atmosphere_json,
            profile.service_features_json, profile.evidence_summary,
        ])
    return " ".join(str(part) for part in parts if part).lower()


def _flatten_json_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        flattened: list[str] = []
        for key, nested in value.items():
            flattened.append(str(key))
            flattened.extend(_flatten_json_values(nested))
        return flattened
    if isinstance(value, (list, tuple, set)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_json_values(item))
        return flattened
    return [str(value)]


def _parse_json_value(raw):
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def place_has_strict_feature_evidence(
    place: Place,
    profile: BusinessAIProfile | None,
    feature: str,
) -> bool:
    """Confirm a requested amenity/service from saved data only.

    First-party Business Studio selections are accepted as direct business
    confirmation. Imported/enriched service-feature fields and explicit saved
    Place.features_json values are also accepted. No live API call is made.
    """
    requested = _normalize_feature_value(feature)
    if not requested:
        return False
    accepted = _feature_alias_normalized_values(requested)

    # 1) Business-owner selections stored under features_json.owner_provided.data.
    parsed_features = _parse_json_value(place.features_json)
    if isinstance(parsed_features, dict):
        owner_wrapper = parsed_features.get("owner_provided")
        owner_data = owner_wrapper.get("data") if isinstance(owner_wrapper, dict) else None
        if isinstance(owner_data, dict):
            if requested == "parking":
                parking = owner_data.get("parking")
                if isinstance(parking, list) and any(str(item).strip() for item in parking):
                    return True
            owner_values = {
                _normalize_feature_value(value)
                for value in _flatten_json_values(owner_data)
            }
            owner_values.discard("")
            if owner_values & accepted:
                return True

    # 2) Structured imported/enriched service features.
    if profile and profile.service_features_json:
        service_values = {
            _normalize_feature_value(value)
            for value in _flatten_json_values(_parse_json_value(profile.service_features_json))
        }
        service_values.discard("")
        if requested == "parking" and any("parking" in value for value in service_values):
            return True
        if service_values & accepted:
            return True

    # 3) Explicit saved imported features (not generic description/search text).
    feature_values = {
        _normalize_feature_value(value)
        for value in _flatten_json_values(parsed_features)
    }
    feature_values.discard("")
    if requested == "parking" and any("parking" in value for value in feature_values):
        return True
    return bool(feature_values & accepted)



def profile_has_strict_dish_evidence(profile: BusinessAIProfile | None, dish: str) -> bool:
    """Return True only when saved menu-focused AI research supports a dish.

    Generic business text, search tags, names, ratings, and category labels are
    deliberately excluded. A specific dish is a hard requirement and must be
    backed by menu/signature/reputation evidence with at least medium menu
    confidence.
    """
    if profile is None:
        return False
    if (profile.menu_confidence or "low").lower() not in {"medium", "high"}:
        return False
    # Only official-menu fields qualify as availability proof. Evidence summaries
    # and review text can contain phrases such as "gnocchi was not verified", so
    # they must never be used for the hard availability gate.
    evidence_text = " ".join(str(value) for value in [
        profile.menu_items_json,
        profile.signature_items_json,
    ] if value).lower()
    return re.search(rf"\b{re.escape(dish.lower())}\b", evidence_text) is not None


def _normalize_dietary_value(value) -> str:
    """Normalize saved dietary labels without turning 'halal options' into 'halal'."""
    if isinstance(value, dict):
        value = (
            value.get("status")
            or value.get("name")
            or value.get("option")
            or value.get("label")
            or value.get("value")
            or ""
        )
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def profile_has_strict_dietary_evidence(
    profile: BusinessAIProfile | None,
    option: str,
) -> bool:
    """Require saved, source-backed dietary evidence.

    A generic "halal_options" value is NOT treated as a verified halal restaurant.
    This reads saved knowledge only and never triggers live research.
    """
    if profile is None or not option:
        return False

    try:
        dietary_options = json.loads(profile.dietary_options_json or "[]")
    except (TypeError, json.JSONDecodeError):
        dietary_options = []

    try:
        source_urls = json.loads(profile.source_urls_json or "[]")
    except (TypeError, json.JSONDecodeError):
        source_urls = []

    requested = _normalize_dietary_value(option)
    if not requested:
        return False

    values = {
        _normalize_dietary_value(value)
        for value in (dietary_options if isinstance(dietary_options, list) else [])
    }
    values.discard("")

    if requested == "halal":
        accepted = {
            "halal",
            "fully_halal",
            "verified_halal",
            "certified_halal",
            "halal_restaurant",
            "halal_meat",
        }
        option_confirmed = bool(values & accepted)
    else:
        accepted = {
            requested,
            f"verified_{requested}",
            f"certified_{requested}",
        }
        option_confirmed = bool(values & accepted)

    confidence_ok = str(profile.confidence or "low").lower() in {"medium", "high"}
    sources_ok = isinstance(source_urls, list) and any(
        str(url).strip() for url in source_urls
    )

    return option_confirmed and confidence_ok and sources_ok

def profile_matches_strict_requirements(
    profile: BusinessAIProfile | None,
    filters: AISearchFilters,
) -> bool:
    """Return True only when every evidence-sensitive request is verified."""
    dishes_ok = all(
        profile_has_strict_dish_evidence(profile, dish)
        for dish in filters.requested_dishes
    )
    dietary_ok = all(
        profile_has_strict_dietary_evidence(profile, option)
        for option in filters.dietary_options
    )
    price_ok = profile_has_strict_price_evidence(
        profile,
        filters.maximum_price,
    )
    return dishes_ok and dietary_ok and price_ok


def profile_has_strict_price_evidence(
    profile: BusinessAIProfile | None,
    maximum_price: float | None,
) -> bool:
    """Require a researched numeric main-course price for a hard price cap."""
    if maximum_price is None:
        return True
    if profile is None or profile.average_main_price_cad is None:
        return False
    if (profile.price_confidence or "low").lower() not in {"medium", "high"}:
        return False
    return float(profile.average_main_price_cad) <= maximum_price

def is_real_restaurant_candidate(place: Place, profile: BusinessAIProfile | None, requested_dishes: list[str]) -> bool:
    text = combined_business_text(place, profile)
    # Strongly reject obvious non-restaurant businesses, unless enrichment
    # explicitly confirms a requested dish/menu match.
    has_requested_dish = any(re.search(rf"\b{re.escape(dish)}\b", text) for dish in requested_dishes)
    if any(term in text for term in NON_RESTAURANT_TERMS) and not has_requested_dish:
        return False
    # A dish-specific request should not be satisfied by a business whose
    # stored identity is a different narrow food format unless menu evidence
    # confirms the requested dish.
    narrow_food_formats = {"sandwich", "pizza", "falafel", "shawarma", "subs"}
    if requested_dishes and not has_requested_dish:
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in narrow_food_formats):
            return False
    restaurant_signal = any(term in text for term in (
        "restaurant", "trattoria", "osteria", "bistro", "ristorante",
        "dining", "cafe", "eatery", "bar & grill", "grill",
    ))
    return restaurant_signal or has_requested_dish


def price_matches_budget(place: Place, profile: BusinessAIProfile | None, budget: str | None) -> bool | None:
    if not budget:
        return None
    values = " ".join(str(value) for value in [
        place.price_range,
        profile.price_level if profile else None,
        profile.value_for_money if profile else None,
        profile.average_main_price_cad if profile else None,
    ] if value is not None).lower()
    if not values.strip():
        return None
    if budget == "affordable":
        return any(token in values for token in ("$", "cheap", "affordable", "budget", "good", "excellent")) and "$$$$" not in values
    if budget == "upscale":
        return any(token in values for token in ("$$$", "$$$$", "upscale", "luxury", "fine"))
    return None


def positive_dish_review_evidence(profile: BusinessAIProfile | None, dish: str) -> str | None:
    if profile is None:
        return None
    try:
        rows = json.loads(profile.dish_reputation_json or "[]")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item", "")).lower()
        sentiment = str(row.get("sentiment", "")).lower()
        confidence = str(row.get("confidence", "low")).lower()
        if dish.lower() in item and sentiment == "positive" and confidence in {"medium", "high"}:
            evidence = str(row.get("evidence", "")).strip()
            return evidence or f"Customer reviews are positive about {dish}"
    return None


def score_candidate(
    place: Place,
    profile: BusinessAIProfile | None,
    filters: AISearchFilters,
    distance_km: float | None = None,
) -> tuple[int, list[str], str]:
    text = combined_business_text(place, profile)
    score = 25.0
    reasons: list[str] = []

    cuisine_match = False
    if filters.requested_cuisine:
        aliases = cuisine_terms(filters.requested_cuisine)
        cuisine_match = any(re.search(rf"\b{re.escape(term)}\b", text) is not None for term in aliases)
        if cuisine_match:
            score += 30
            reasons.append(f"Confirmed {filters.requested_cuisine} match")
        else:
            score -= 28

    dish_matches = [dish for dish in filters.requested_dishes if re.search(rf"\b{re.escape(dish)}\b", text)]
    if filters.requested_dishes:
        if dish_matches:
            score += 28
            pretty = ", ".join(item.title() for item in dish_matches)
            reasons.append(f"{pretty} confirmed on an official menu")
            for dish in dish_matches:
                review_evidence = positive_dish_review_evidence(profile, dish)
                if review_evidence:
                    score += 10
                    reasons.append(f"Customer reviews are positive about {dish}")
                    break
        elif profile:
            score -= 12
        else:
            score -= 4

    budget_match = price_matches_budget(place, profile, filters.budget_preference)
    if filters.maximum_price is not None:
        known_price = profile.average_main_price_cad if profile else None
        if known_price is not None:
            if float(known_price) <= filters.maximum_price:
                score += 14
                reasons.append(f"Average main price is within ${filters.maximum_price:g}")
            else:
                score -= 18
        elif place.price_range:
            # A symbolic price range is weaker evidence than a menu price.
            if str(place.price_range).strip() == "$":
                score += 4
    if budget_match is True:
        score += 12
        reasons.append("Pricing appears to match your budget")
    elif budget_match is False:
        score -= 10

    for preference in filters.atmosphere:
        if preference.lower() in text:
            score += 8
            reasons.append(f"Matches {preference} atmosphere")
    for option in filters.dietary_options:
        if profile_has_strict_dietary_evidence(profile, option):
            score += 18
            if _normalize_dietary_value(option) == "halal":
                reasons.append("Verified halal evidence")
            else:
                reasons.append(f"Verified {option} evidence")
    for feature in filters.requested_features:
        if place_has_strict_feature_evidence(place, profile, feature):
            score += 16
            label = FEATURE_DISPLAY_NAMES.get(_normalize_feature_value(feature), str(feature).replace("_", " "))
            reasons.append(f"Confirmed {label}")
    if filters.language and filters.language.lower() in text:
        score += 10
        reasons.append(f"{filters.language} language match")

    rating = float(place.rating or 0)
    reviews = int(place.review_count or 0)
    score += max(0, rating - 3.5) * 8
    score += min(10, (reviews ** 0.5) / 5) if reviews > 0 else 0
    if rating >= 4.5:
        reasons.append(f"Strong {rating:.1f}★ rating")
    if reviews >= 250:
        reasons.append(f"Backed by {reviews:,} reviews")

    if distance_km is not None:
        score += max(0, 8 - min(distance_km, 8))
        reasons.append(f"{distance_km:.1f} km away")

    if profile:
        confidence = profile.confidence or "low"
        score += {"high": 8, "medium": 4, "low": 1}.get(confidence.lower(), 0)
        if profile.ai_summary:
            reasons.append(profile.ai_summary[:120].rstrip(" ."))
    else:
        confidence = "limited"

    score = int(max(1, min(99, round(score))))
    # Request-specific reasons only; never claim an unverified match.
    if not reasons:
        reasons.append("Closest available match from the stored business data")
    return score, reasons[:4], confidence


def get_profiles_for_places(session: Session, places: list[Place]) -> dict[int, BusinessAIProfile]:
    place_ids = [place.id for place in places if place.id is not None]
    if not place_ids:
        return {}
    profiles = list(session.exec(select(BusinessAIProfile).where(BusinessAIProfile.place_id.in_(place_ids))).all())
    return {profile.place_id: profile for profile in profiles}


def _candidate_matches_cuisine(place: Place, profile: BusinessAIProfile | None, cuisine: str | None) -> bool:
    if not cuisine:
        return True
    text = combined_business_text(place, profile)
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in cuisine_terms(cuisine))


def _research_target_key(filters: AISearchFilters) -> str:
    # Include the research prompt version so fixes invalidate stale negative cache rows.
    payload = {
        "prompt_version": PROMPT_VERSION,
        "cuisine": (filters.requested_cuisine or "").strip().lower(),
        "dishes": sorted(item.strip().lower() for item in filters.requested_dishes if item.strip()),
        "dietary_options": sorted(
            item.strip().lower()
            for item in filters.dietary_options
            if item.strip()
        ),
        "maximum_price": filters.maximum_price,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _cached_research_place_ids(session: Session, places: list[Place], target_key: str) -> set[int]:
    """Return only fresh cache rows.

    Positive findings stay reusable for 30 days. Negative findings expire after
    24 hours because menus and search coverage can change. Failed attempts are
    never treated as completed research and are retried after a short delay.
    """
    place_ids = [place.id for place in places if place.id is not None]
    if not place_ids:
        return set()
    rows = session.exec(
        select(BusinessResearchCache).where(
            BusinessResearchCache.place_id.in_(place_ids),
            BusinessResearchCache.target_key == target_key,
            BusinessResearchCache.status == "completed",
        )
    ).all()
    now = utc_now()
    fresh: set[int] = set()
    for row in rows:
        ttl = timedelta(days=30 if row.matched else 1)
        if row.researched_at and now - row.researched_at <= ttl:
            fresh.add(row.place_id)
    return fresh


def _save_research_cache(
    session: Session,
    place: Place,
    filters: AISearchFilters,
    target_key: str,
    matched: bool,
    error_message: str | None = None,
) -> None:
    row = session.exec(
        select(BusinessResearchCache).where(
            BusinessResearchCache.place_id == place.id,
            BusinessResearchCache.target_key == target_key,
        )
    ).first()
    if row is None:
        row = BusinessResearchCache(place_id=place.id, target_key=target_key)
    row.requested_cuisine = filters.requested_cuisine
    row.requested_dishes_json = _json_dump(filters.requested_dishes)
    row.maximum_price = filters.maximum_price
    row.status = "failed" if error_message else "completed"
    row.matched = matched
    row.error_message = error_message
    row.researched_at = utc_now()
    session.add(row)



def _research_candidate_priority(
    place: Place,
    profile: BusinessAIProfile | None,
    filters: AISearchFilters,
) -> tuple[int, float, int]:
    """Prioritize likely, researchable candidates without spending AI tokens.

    Strong signals:
    - requested cuisine appears in imported or saved data;
    - an official menu link or website exists;
    - existing knowledge already contains relevant dish-family terms;
    - higher rating and review count.
    """
    text = combined_business_text(place, profile)
    score = 0

    if filters.requested_cuisine and _candidate_matches_cuisine(
        place, profile, filters.requested_cuisine
    ):
        score += 100

    if place.menu_link:
        score += 40
    elif place.website:
        score += 20

    for option in filters.dietary_options:
        normalized_option = option.strip().lower()
        if normalized_option and re.search(
            rf"\b{re.escape(normalized_option)}\b",
            text,
        ):
            score += 45

    for dish in filters.requested_dishes:
        normalized = dish.lower()
        if re.search(rf"\b{re.escape(normalized)}\b", text):
            score += 35
        elif normalized in {
            "penne", "spaghetti", "fettuccine", "linguine",
            "rigatoni", "tagliatelle", "tortellini", "ravioli",
            "gnocchi", "carbonara", "lasagna",
        } and "pasta" in text:
            score += 12

    status_text = str(place.business_status or "").lower()
    if any(term in status_text for term in ("closed", "coming soon", "not open")):
        score -= 200

    return (
        score,
        float(place.rating or 0),
        int(place.review_count or 0),
    )


def research_missing_candidates(
    session: Session,
    places: list[Place],
    filters: AISearchFilters,
    user_latitude: float | None = None,
    user_longitude: float | None = None,
) -> dict[str, int]:
    """Research candidates in waves until enough verified matches are found.

    Positive and negative outcomes are cached by business + request target, so a
    repeated search does not call the web again.
    """
    stats = {"researched": 0, "cached": 0, "matched": 0, "failed": 0}
    if not (
        filters.requested_dishes
        or filters.dietary_options
        or filters.maximum_price is not None
    ):
        return stats

    target_key = _research_target_key(filters)
    profiles = get_profiles_for_places(session, places)
    cached_ids = _cached_research_place_ids(session, places, target_key)
    stats["cached"] = len(cached_ids)

    # Count matches already available from prior research.
    for place in places:
        profile = profiles.get(place.id) if place.id is not None else None
        if (
            place.id in cached_ids
            and profile_matches_strict_requirements(profile, filters)
        ):
            stats["matched"] += 1

    candidates: list[Place] = []
    for place in places:
        if place.id is None or place.id in cached_ids:
            continue
        profile = profiles.get(place.id)
        if filters.category and filters.category.lower() == "restaurant" and not is_real_restaurant_candidate(place, profile, []):
            continue
        if not _candidate_matches_cuisine(place, profile, filters.requested_cuisine):
            continue

        # A strict dish claim requires official evidence. The low-cost
        # enrichment engine can verify that evidence only when the business has
        # an official website or menu URL, so skip candidates that cannot be
        # verified instead of spending an AI call on them.
        if (
            filters.requested_dishes
            or filters.dietary_options
            or filters.maximum_price is not None
        ) and not (place.menu_link or place.website):
            continue

        candidates.append(place)

    if user_latitude is not None and user_longitude is not None:
        # For a "near me" request, research the closest verifiable businesses
        # first. Rating and existing evidence are tie-breakers only. Previously,
        # high-rated businesses anywhere in Ottawa could consume the research
        # budget before genuinely nearby restaurants were checked.
        def near_me_research_key(place: Place) -> tuple[float, int, float, int]:
            if place.latitude is None or place.longitude is None:
                distance = float("inf")
            else:
                distance = calculate_distance_km(
                    user_latitude,
                    user_longitude,
                    place.latitude,
                    place.longitude,
                )

            priority = _research_candidate_priority(
                place,
                profiles.get(place.id) if place.id is not None else None,
                filters,
            )
            return (
                distance,
                -priority[0],
                -priority[1],
                -priority[2],
            )

        candidates.sort(key=near_me_research_key)
    else:
        candidates.sort(
            key=lambda place: _research_candidate_priority(
                place,
                profiles.get(place.id) if place.id is not None else None,
                filters,
            ),
            reverse=True,
        )

    candidates = candidates[:RESEARCH_MAX_CANDIDATES]

    for offset in range(0, len(candidates), RESEARCH_BATCH_SIZE):
        if stats["matched"] >= RESEARCH_TARGET_RESULTS:
            break
        batch = candidates[offset:offset + RESEARCH_BATCH_SIZE]
        if not batch:
            break
        results: list[tuple[Place, dict | None, str | None]] = []
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            future_map = {
                executor.submit(
                    enrich_place, place, True, list(filters.requested_dishes),
                    filters.maximum_price, filters.requested_cuisine,
                ): place for place in batch
            }
            for future in as_completed(future_map):
                place = future_map[future]
                try:
                    results.append((place, future.result(), None))
                except Exception as error:
                    results.append((place, None, str(error)[:1000]))
                    print(f"On-demand research failed for {place.id} {place.name}: {error!r}")

        for place, data, error_message in results:
            stats["researched"] += 1
            if error_message or data is None:
                stats["failed"] += 1
                _save_research_cache(session, place, filters, target_key, False, error_message)
                continue
            save_enrichment_profile(session, place, data)
            session.flush()
            refreshed = session.exec(select(BusinessAIProfile).where(BusinessAIProfile.place_id == place.id)).first()
            matched = profile_matches_strict_requirements(
                refreshed,
                filters,
            )
            _save_research_cache(session, place, filters, target_key, matched)
            if matched:
                stats["matched"] += 1
        session.commit()

    return stats


def rank_candidates(
    session: Session,
    places: list[Place],
    filters: AISearchFilters,
    user_latitude: float | None = None,
    user_longitude: float | None = None,
) -> list[PlaceResult]:
    profiles = get_profiles_for_places(session, places)
    ranked: list[tuple[int, PlaceResult]] = []
    for place in places:
        profile = profiles.get(place.id) if place.id is not None else None
        if filters.category and filters.category.lower() == "restaurant":
            if not is_real_restaurant_candidate(place, profile, filters.requested_dishes):
                continue

        # Specific dishes are hard requirements. Never pad the result list with
        # unrelated highly-rated businesses simply to display five cards.
        if filters.requested_dishes:
            if not all(profile_has_strict_dish_evidence(profile, dish) for dish in filters.requested_dishes):
                continue

        # Dietary requirements such as halal, kosher, vegan, and gluten-free
        # are hard constraints. A nearby or highly rated business must never be
        # shown unless the saved research explicitly confirms every requested
        # option with source-backed evidence.
        if filters.dietary_options:
            if not all(
                profile_has_strict_dietary_evidence(profile, option)
                for option in filters.dietary_options
            ):
                continue

        # Amenities/services such as family-friendly, parking, and patio are
        # also hard conditions. They must be explicitly present in saved data.
        if filters.requested_features:
            if not all(
                place_has_strict_feature_evidence(place, profile, feature)
                for feature in filters.requested_features
            ):
                continue

        # A numeric price cap is also a hard requirement. We only claim "under
        # $X" when saved research contains a numeric average main-course price
        # with medium or high confidence.
        if filters.maximum_price is not None and not profile_has_strict_price_evidence(profile, filters.maximum_price):
            continue
        distance = None
        if user_latitude is not None and user_longitude is not None and place.latitude is not None and place.longitude is not None:
            distance = round(calculate_distance_km(user_latitude, user_longitude, place.latitude, place.longitude), 1)
        score, reasons, confidence = score_candidate(place, profile, filters, distance)
        # Cuisine is a hard constraint when requested. This prevents generic
        # restaurants, grocery stores, and unrelated shops from appearing.
        if filters.requested_cuisine and not any(filters.requested_cuisine.lower() in reason.lower() for reason in reasons):
            continue
        result = convert_place_to_result(place, distance_km=distance)
        result.match_score = score
        result.match_reasons = reasons
        result.confidence = confidence
        result.enrichment_status = "enriched" if profile else "not_enriched"
        result.ai_summary = profile.ai_summary if profile else None
        ranked.append((score, result))
    if user_latitude is not None and user_longitude is not None:
        ranked.sort(
            key=lambda item: (
                item[1].distance_km
                if item[1].distance_km is not None
                else float("inf"),
                -item[0],
                -(item[1].rating or 0),
                -(item[1].review_count or 0),
            )
        )
    else:
        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].rating or 0,
                item[1].review_count or 0,
            ),
            reverse=True,
        )
    return [item[1] for item in ranked]


def _distance_for_place(
    place: Place,
    user_latitude: float,
    user_longitude: float,
) -> float | None:
    if place.latitude is None or place.longitude is None:
        return None
    return calculate_distance_km(
        user_latitude,
        user_longitude,
        place.latitude,
        place.longitude,
    )


def progressive_near_me_search(
    session: Session,
    places: list[Place],
    filters: AISearchFilters,
    user_latitude: float,
    user_longitude: float,
    *,
    stop_after_target: bool = True,
    result_limit: int | None = None,
) -> tuple[list[PlaceResult], list[dict], float]:
    """0.5 -> 1 -> 2 -> 3 -> 5 -> 7.5 -> 10 -> 15 -> 20 km.

    Saved PostgreSQL knowledge only. No live enrichment/API research.
    """
    distance_by_id: dict[int, float] = {}
    gps_places: list[Place] = []

    for place in places:
        if place.id is None:
            continue
        distance = _distance_for_place(place, user_latitude, user_longitude)
        if distance is None:
            continue
        distance_by_id[place.id] = distance
        gps_places.append(place)

    gps_places.sort(key=lambda p: distance_by_id.get(p.id, float("inf")))

    stages: list[dict] = []
    selected_results: list[PlaceResult] = []
    stopping_radius = PROGRESSIVE_RADII_KM[-1]

    for radius in PROGRESSIVE_RADII_KM:
        in_radius = [
            place for place in gps_places
            if distance_by_id.get(place.id, float("inf")) <= radius
        ]

        verified = rank_candidates(
            session,
            in_radius,
            filters,
            user_latitude=user_latitude,
            user_longitude=user_longitude,
        )

        profiles = get_profiles_for_places(session, in_radius)
        known_count = sum(
            1 for place in in_radius
            if place.id is not None and profiles.get(place.id) is not None
        )
        unknown_count = max(0, len(in_radius) - known_count)

        stages.append({
            "radius_km": radius,
            "restaurants": len(in_radius),
            "knowledge_known": known_count,
            "knowledge_unknown": unknown_count,
            "verified_matches": len(verified),
        })

        effective_limit = result_limit or PROGRESSIVE_DISPLAY_LIMIT
        selected_results = verified[:effective_limit]
        stopping_radius = radius

        if stop_after_target and len(verified) >= PROGRESSIVE_TARGET_RESULTS:
            break

    return selected_results, stages, stopping_radius


def _format_radius(radius: float) -> str:
    return str(int(radius)) if float(radius).is_integer() else f"{radius:g}"


def build_progressive_explanation(
    stages: list[dict],
    requested_label: str,
) -> str:
    if not stages:
        return "No businesses with usable GPS coordinates were available."

    parts = [
        "Progressive radius search used saved PostgreSQL knowledge only; "
        "no live enrichment/API research was run."
    ]
    for stage in stages:
        parts.append(
            f"{_format_radius(stage['radius_km'])} km: "
            f"{stage['restaurants']} restaurants, "
            f"{stage['verified_matches']} verified {requested_label} match"
            f"{'es' if stage['verified_matches'] != 1 else ''}, "
            f"{stage['knowledge_unknown']} still unknown."
        )
    return " ".join(parts)


def build_progressive_message(
    results: list[PlaceResult],
    requested_label: str,
) -> str:
    if not results:
        return (
            f"I couldn't confirm a verified {requested_label} near you from the "
            "knowledge currently saved in the database. Unknown businesses were "
            "not treated as non-matches."
        )

    within_one_km = [
        result for result in results
        if result.distance_km is not None and result.distance_km <= 1.0
    ]

    if within_one_km:
        farther = len(results) - len(within_one_km)
        message = (
            f"I found {len(within_one_km)} verified {requested_label} "
            f"option{'s' if len(within_one_km) != 1 else ''} within 1 km."
        )
        if farther:
            farthest = max(result.distance_km or 0 for result in results)
            message += (
                f" I also found {farther} additional verified option"
                f"{'s' if farther != 1 else ''} farther away, up to "
                f"{farthest:.1f} km."
            )
        return message

    closest = results[0].distance_km
    farthest = max(result.distance_km or 0 for result in results)
    if closest is None:
        return (
            f"I found {len(results)} verified {requested_label} option"
            f"{'s' if len(results) != 1 else ''}."
        )
    return (
        f"I found {len(results)} verified {requested_label} option"
        f"{'s' if len(results) != 1 else ''}. "
        f"The closest is {closest:.1f} km away"
        + (
            f", and the displayed verified options extend to {farthest:.1f} km."
            if len(results) > 1 else "."
        )
    )


def convert_place_to_result(
    place: Place,
    distance_km: float | None = None,
) -> PlaceResult:
    """
    Convert a database Place object into the public
    AI search response format.
    """

    if place.id is None:
        raise ValueError(
            "A saved place must have an ID."
        )

    return PlaceResult(
        id=place.id,
        business_id=place.business_id,
        place_id=place.place_id,
        name=place.name,
        category=place.category,
        full_address=place.full_address,
        city=place.city,
        state=place.state,
        postal_code=place.postal_code,
        country=place.country,
        latitude=place.latitude,
        longitude=place.longitude,
        rating=place.rating,
        review_count=place.review_count,
        phone_number=place.phone_number,
        website=place.website,
        google_maps_url=(
            place.google_maps_url
        ),
        photo_url=place.photo_url,
        logo_url=place.logo_url,
        street_view_url=place.street_view_url,
        business_type=place.business_type,
        subtypes=place.subtypes,
        price_range=place.price_range,
        working_hours_json=place.working_hours_json,
        features_json=place.features_json,
        verified=place.verified,
        description=place.description,
        distance_km=distance_km,
    )


def sort_places_by_distance(
    places: list[Place],
    user_latitude: float,
    user_longitude: float,
) -> list[PlaceResult]:
    """
    Calculate the distance from the user to every
    business and return the nearest businesses first.
    """

    places_with_distance: list[
        PlaceResult
    ] = []

    for place in places:
        if (
            place.latitude is None
            or place.longitude is None
        ):
            continue

        distance = calculate_distance_km(
            latitude_1=user_latitude,
            longitude_1=user_longitude,
            latitude_2=place.latitude,
            longitude_2=place.longitude,
        )

        result = convert_place_to_result(
            place=place,
            distance_km=round(
                distance,
                1,
            ),
        )

        places_with_distance.append(
            result
        )

    places_with_distance.sort(
        key=lambda place: (
            (
                place.distance_km
                if place.distance_km
                is not None
                else float("inf")
            ),
            -(place.rating or 0),
            -(place.review_count or 0),
        )
    )

    return places_with_distance


def create_result_message(
    assistant_message: str,
    result_count: int,
    category: str | None,
    used_location: bool,
) -> str:
    """
    Add the actual database result count to the
    assistant's conversational message.
    """

    normalized_message = (
        assistant_message.strip()
        if assistant_message
        else ""
    )

    business_name = (
        category
        if category
        else "business"
    )

    if result_count == 0:
        if used_location:
            return (
                f"{normalized_message} "
                f"I could not find matching "
                f"{business_name} options near your "
                f"current location."
            ).strip()

        return (
            f"{normalized_message} "
            f"I could not find matching "
            f"{business_name} options."
        ).strip()

    if result_count == 1:
        result_summary = (
            f"I found 1 matching "
            f"{business_name}."
        )
    else:
        result_summary = (
            f"I found {result_count} matching "
            f"{business_name} options."
        )

    return (
        f"{normalized_message} "
        f"{result_summary}"
    ).strip()


@router.post(
    "/search",
    response_model=AISearchResponse,
)
def ai_search(
    request: AISearchRequest,
    session: Session = Depends(
        get_session
    ),
):
    """
    Understand a natural-language business search,
    use recent conversation history, and return
    matching local businesses.
    """

    user_query = request.query.strip()

    if len(user_query) < 3:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Please enter a longer search "
                "request."
            ),
        )

    has_latitude = (
        request.latitude is not None
    )

    has_longitude = (
        request.longitude is not None
    )

    if has_latitude != has_longitude:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Latitude and longitude must be "
                "provided together."
            ),
        )

    has_user_location = (
        has_latitude
        and has_longitude
    )

    conversation_needs_location = (
        conversation_uses_near_me(
            request
        )
    )

    if (
        conversation_needs_location
        and not has_user_location
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Location access is required for "
                "this near-me conversation. Please "
                "allow location access or enter a "
                "city."
            ),
        )

    # Context-only comparison questions should never invoke the AI planner or
    # start a fresh business search.  They operate exclusively on result cards
    # already shown in this chat.
    prior_result_ids = previously_displayed_result_ids(request.messages)
    if query_asks_closest_from_previous(user_query) and prior_result_ids:
        rows = session.exec(
            select(Place).where(Place.id.in_(prior_result_ids))
        ).all()
        by_id = {place.id: place for place in rows if place.id is not None}
        prior_places = [
            by_id[result_id]
            for result_id in prior_result_ids
            if result_id in by_id
        ]

        contextual_results: list[PlaceResult] = []
        for place in prior_places:
            distance = None
            if (
                has_user_location
                and place.latitude is not None
                and place.longitude is not None
            ):
                distance = round(
                    calculate_distance_km(
                        request.latitude,
                        request.longitude,
                        place.latitude,
                        place.longitude,
                    ),
                    1,
                )
            result = convert_place_to_result(place, distance_km=distance)
            contextual_results.append(result)

        distance_results = [
            result
            for result in contextual_results
            if result.distance_km is not None
        ]
        if distance_results:
            closest = min(
                distance_results,
                key=lambda result: result.distance_km,
            )
            context_filters = AISearchFilters(
                category="restaurant",
                context_mode="conversation_compare",
                explanation=(
                    f"Compared only the {len(prior_result_ids)} restaurant "
                    "results already shown in this conversation; no new "
                    "restaurant search or AI research was run."
                ),
            )
            return AISearchResponse(
                query=user_query,
                assistant_message=(
                    f"{closest.name} is the closest of the restaurants already "
                    f"shown, at {closest.distance_km:.1f} km away."
                ),
                filters=context_filters,
                results=[closest],
            )

    try:
        extracted = understand_search_query(
            user_query=user_query,
            messages=request.messages,
        )

    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "The AI returned invalid JSON."
            ),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except Exception as error:
        print(
            "AI search error:",
            repr(error),
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "AI search is temporarily "
                "unavailable."
            ),
        ) from error

    filters = AISearchFilters(
        category=extracted.get(
            "category"
        ),
        city=normalize_city(
            extracted.get("city")
        ),
        search=extracted.get(
            "search"
        ),
        requested_cuisine=extracted.get("requested_cuisine"),
        requested_dishes=list(extracted.get("requested_dishes") or []),
        budget_preference=extracted.get("budget_preference"),
        maximum_price=extracted.get("maximum_price"),
        atmosphere=list(extracted.get("atmosphere") or []),
        dietary_options=list(extracted.get("dietary_options") or []),
        requested_features=[],
        open_now=extracted.get("open_now"),
        language=extracted.get("language"),
        context_mode=extracted.get("context_mode") or "standalone",
        minimum_rating=(
            normalize_minimum_rating(
                extracted.get(
                    "minimum_rating"
                )
            )
        ),
        minimum_review_count=(
            normalize_minimum_review_count(
                extracted.get(
                    "minimum_review_count"
                )
            )
        ),
        urgency=extracted.get(
            "urgency"
        ),
        explanation=extracted.get(
            "explanation"
        ),
    )

    # Preserve hard conditions on terse conversational follow-ups such as
    # "find 2 more" even if the query planner omits them.
    inherit_dietary_from_history_if_needed(filters, request)

    # Hard dietary intent must never disappear because of an AI-planner miss or
    # a common user typo.  Merge deterministic dietary signals from the raw query.
    inferred_dietary = infer_dietary_options_from_query(user_query)
    if inferred_dietary:
        existing_dietary = {
            _normalize_dietary_value(value)
            for value in filters.dietary_options
            if _normalize_dietary_value(value)
        }
        for option in inferred_dietary:
            if _normalize_dietary_value(option) not in existing_dietary:
                filters.dietary_options.append(option)

    # Amenities/services are a separate hard-filter domain. The query planner
    # can occasionally classify "family-friendly" as dietary or atmosphere;
    # deterministically move those terms into requested_features instead.
    inferred_features = infer_requested_features_from_query(user_query)
    if inferred_features:
        filters.requested_features = list(dict.fromkeys(inferred_features))
        feature_aliases = set().union(
            *(_feature_alias_normalized_values(feature) for feature in filters.requested_features)
        )
        filters.dietary_options = [
            option for option in filters.dietary_options
            if _normalize_feature_value(option) not in feature_aliases
        ]
        filters.atmosphere = [
            option for option in filters.atmosphere
            if _normalize_feature_value(option) not in feature_aliases
        ]

    inherit_features_from_history_if_needed(filters, request)

    # The AI planner is authoritative. Regex extraction is only a safety fallback
    # when a model field is unexpectedly empty.
    fallback_cuisine, fallback_dishes, fallback_budget = extract_request_preferences(user_query, filters.search)
    if not filters.requested_cuisine:
        filters.requested_cuisine = fallback_cuisine
    if not filters.requested_dishes:
        filters.requested_dishes = fallback_dishes
    if not filters.budget_preference:
        filters.budget_preference = fallback_budget
    if filters.requested_cuisine and filters.requested_cuisine.lower() in {"iranian", "persian"}:
        filters.requested_cuisine = "Persian"
    if not filters.requested_cuisine:
        for dish in filters.requested_dishes:
            hinted_cuisine = DISH_CUISINE_HINTS.get(dish.lower())
            if hinted_cuisine:
                filters.requested_cuisine = hinted_cuisine
                break

    assistant_message = (
        extracted.get(
            "assistant_message"
        )
        or filters.explanation
        or (
            "I'll look for matching "
            "businesses."
        )
    )

    # Use GPS only when the effective request is truly a near-me search and
    # no city was explicitly established for the latest search. The frontend
    # may still send saved coordinates from an earlier near-me message; those
    # coordinates must not override a later request such as
    # "show restaurants in Ottawa".
    use_user_location = (
        conversation_needs_location
        and has_user_location
        and not filters.city
    )

    prior_result_ids = previously_displayed_result_ids(request.messages)

    if use_user_location:
        # Progressive-radius near-me search.
        # This path intentionally DOES NOT call research_missing_candidates()
        # or enrich_place(). Unknown remains UNKNOWN.
        candidate_filters = copy_search_filters(
            filters,
            search=None if (
                filters.requested_dishes
                or filters.dietary_options
                or filters.requested_features
            ) else filters.search,
        )

        database_places = run_place_query(
            session,
            candidate_filters,
            include_city=False,
            result_limit=10000,
        )

        is_more_followup = query_requests_more(user_query)
        more_count = requested_more_count(user_query) if is_more_followup else None
        shown_ids = previously_displayed_result_ids(request.messages) if is_more_followup else []
        previous_count = len(shown_ids) if shown_ids else (
            previous_displayed_count(request.messages) if is_more_followup else 0
        )

        # A "more" request is pagination over the same verified result set.
        # Search deeply enough to find new IDs beyond everything already shown.
        search_result_limit = (previous_count + (more_count or 0) + 10) if is_more_followup else None
        results, radius_stages, stopping_radius = progressive_near_me_search(
            session,
            database_places,
            filters,
            user_latitude=request.latitude,
            user_longitude=request.longitude,
            stop_after_target=not is_more_followup,
            result_limit=search_result_limit,
        )

        if is_more_followup:
            all_verified = results
            if shown_ids:
                shown_id_set = set(shown_ids)
                unseen = [result for result in all_verified if result.id not in shown_id_set]
                results = unseen[:(more_count or 5)]
            else:
                # Backward-compatible fallback for conversations created before
                # result IDs were attached to assistant turns.
                results = all_verified[previous_count:previous_count + (more_count or 5)]

        requested_parts = [
            *(FEATURE_DISPLAY_NAMES.get(_normalize_feature_value(value), str(value).replace("_", " ")) for value in filters.requested_features),
            *filters.dietary_options,
            *filters.requested_dishes,
        ]
        if filters.requested_cuisine:
            requested_parts.append(filters.requested_cuisine)
        if filters.category:
            requested_parts.append(filters.category)

        requested_label = " ".join(
            str(value).strip()
            for value in requested_parts
            if str(value).strip()
        ) or "matching local business"

        requested_label = re.sub(
            r"\b(halal)\s+\1\b",
            r"\1",
            requested_label,
            flags=re.IGNORECASE,
        )

        if is_more_followup:
            if results:
                assistant_message = (
                    f"Here are {len(results)} more verified {requested_label} option"
                    f"{'s' if len(results) != 1 else ''}. I excluded the "
                    f"{previous_count} result{'s' if previous_count != 1 else ''} "
                    "already shown in this conversation."
                )
            else:
                assistant_message = (
                    f"I couldn't find any more verified {requested_label} options "
                    "within the search radius after excluding the results already shown."
                )
        else:
            assistant_message = build_progressive_message(
                results,
                requested_label,
            )

        filters.explanation = build_progressive_explanation(
            radius_stages,
            requested_label,
        )
        if is_more_followup:
            filters.explanation = (
                f"Conversational continuation: skipped {previous_count} previously "
                f"displayed verified results and requested {more_count} more. "
                + (filters.explanation or "")
            )

        return AISearchResponse(
            query=user_query,
            assistant_message=assistant_message,
            filters=filters,
            results=results,
        )

    # Candidate retrieval is intentionally broad; request-specific ranking
    # then applies cuisine, dish, budget, rating, enrichment, and distance.
    # This prevents SQL keyword matching from presenting grocery stores or
    # unrelated businesses as strong recommendations.
    # Imported business rows rarely contain individual dish names such as
    # "penne". Using the dish as a SQL keyword can therefore create an empty or
    # misleading candidate set. For a dish request, retrieve the category/city
    # pool broadly, then use cuisine hints, saved knowledge, menu availability,
    # rating, and reviews to prioritize research.
    candidate_keyword = (
        None
        if (filters.requested_dishes or filters.dietary_options or filters.requested_features)
        else filters.search
    )

    candidate_filters = copy_search_filters(
        filters,
        search=candidate_keyword,
    )
    database_places = run_place_query(
        session,
        candidate_filters,
        include_city=True,
        result_limit=500,
    )

    # If the planner returned an overly restrictive keyword or cuisine is not
    # stored consistently, preserve category and city but remove free-text
    # search. The evidence-aware pipeline will still enforce cuisine and dish
    # requirements before displaying results.
    if not database_places and (filters.requested_cuisine or filters.requested_dishes):
        candidate_filters = copy_search_filters(filters, search=None)
        database_places = run_place_query(
            session,
            candidate_filters,
            include_city=True,
            result_limit=500,
        )

    research_stats = research_missing_candidates(session, database_places, filters)
    ranked_results = rank_candidates(session, database_places, filters)
    results = ranked_results[:25]

    enriched_count = sum(1 for result in results if result.enrichment_status == "enriched")
    dish_text = ", ".join(filters.requested_dishes)
    if results:
        verified_parts = []
        if filters.requested_cuisine:
            verified_parts.append(filters.requested_cuisine)
        if dish_text and any(any(dish.lower() in " ".join(result.match_reasons).lower() for dish in filters.requested_dishes) for result in results):
            verified_parts.append(dish_text)
        for option in filters.dietary_options:
            if all(
                option.lower() in " ".join(result.match_reasons).lower()
                for result in results
            ):
                verified_parts.append(option)
        verified_label = " and ".join(verified_parts) or (filters.category or "local business")
        assistant_message = f"I found {len(results)} relevant {verified_label} option{'s' if len(results) != 1 else ''}."
        if filters.requested_dishes and not any(any(dish.lower() in " ".join(result.match_reasons).lower() for dish in filters.requested_dishes) for result in results):
            assistant_message += f" I could confirm the {filters.requested_cuisine or filters.category or 'business'} match, but {dish_text} is not verified yet for these places."
        if (filters.budget_preference or filters.maximum_price is not None) and not any("budget" in " ".join(result.match_reasons).lower() or "pricing" in " ".join(result.match_reasons).lower() or "price" in " ".join(result.match_reasons).lower() for result in results):
            assistant_message += " Pricing is not verified yet, so check the menu before visiting."
        filters.explanation = (
            f"Ranked by request relevance, official menu evidence, review evidence, rating, and review count. "
            f"{enriched_count} displayed matches use saved AI research; {research_stats["researched"]} businesses were researched during this search and {research_stats["cached"]} prior research results were reused."
        )
    else:
        if filters.requested_dishes:
            requested = ", ".join(filters.requested_dishes)
            price_text = f" under ${filters.maximum_price:g}" if filters.maximum_price is not None else ""
            if research_stats["failed"] and research_stats["researched"] == research_stats["failed"]:
                assistant_message = (
                    f"I tried to research {requested}{price_text}, but the live research service failed for all "
                    "candidates. Please check the backend terminal for the exact OpenAI error and try again."
                )
            else:
                assistant_message = (
                    f"I checked up to {RESEARCH_MAX_CANDIDATES} of the strongest verifiable candidates "
                    f"but couldn't confirm {requested}{price_text} in "
                    f"{filters.city or 'the selected area'}. I did not show unrelated businesses."
                )
            filters.explanation = (
                f"Research summary: {research_stats['researched']} attempted, {research_stats['failed']} failed, "
                f"{research_stats['cached']} fresh cached results reused, and {research_stats['matched']} verified matches found. "
                "Specific dishes require official menu evidence, and numeric price limits require verified menu pricing."
            )
        elif filters.dietary_options:
            requested = ", ".join(filters.dietary_options)
            assistant_message = (
                f"I checked up to {RESEARCH_MAX_CANDIDATES} of the strongest "
                f"verifiable candidates but couldn't confirm {requested} in "
                f"{filters.city or 'the selected area'}. I did not show businesses "
                "that lacked evidence."
            )
            filters.explanation = (
                f"Research summary: {research_stats['researched']} attempted, "
                f"{research_stats['failed']} failed, "
                f"{research_stats['cached']} fresh cached results reused, and "
                f"{research_stats['matched']} verified matches found. Dietary "
                "requirements require explicit source-backed evidence."
            )
        else:
            assistant_message = (
                f"I couldn't find a reliable {filters.requested_cuisine or ''} {filters.category or 'business'} match"
                f" in {filters.city or 'the selected area'}. I did not show unrelated businesses."
            ).replace("  ", " ")
            filters.explanation = "No candidates met the required category and cuisine constraints."

    return AISearchResponse(
        query=user_query,
        assistant_message=assistant_message,
        filters=filters,
        results=results,
    )