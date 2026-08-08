import json
import logging
from datetime import datetime, timedelta

import requests

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_user
from dashboard_schemas import (
    BusinessClaimCreate,
    BusinessClaimPublic,
    BusinessProfilePublic,
    BusinessProfileUpdate,
    BusinessLocationUpdate,
    BusinessLocationPublic,
    DashboardOverview,
    BusinessStudioOverview,
    HealthDimension,
    StudioMetric,
    CoachRecommendation,
    ActivityItem,
    MenuItemCreate,
    MenuItemPublic,
    MenuItemUpdate,
)
from models import BusinessClaim, BusinessEvent, BusinessProfile, Favorite, MenuItem, Place, Review, User, utc_now
from menu_icons import infer_menu_icon

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)


def _geocode_business_address(
    full_address: str | None,
    city: str | None,
    postal_code: str | None,
) -> tuple[float, float] | None:
    """Convert a Canadian business address into latitude and longitude.

    Nominatim is used only when a Business Studio profile is saved. A complete
    street address gives the most accurate result, but city and postal code are
    included whenever available.
    """
    address_parts = [
        str(value).strip()
        for value in (full_address, city, postal_code, "Canada")
        if value and str(value).strip()
    ]

    if not full_address or len(address_parts) < 2:
        return None

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": ", ".join(address_parts),
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "ca",
                "addressdetails": 1,
            },
            headers={
                "User-Agent": "AskMyCity/4.0 business-profile-geocoder",
                "Accept-Language": "en",
            },
            timeout=8,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None

        return float(results[0]["lat"]), float(results[0]["lon"])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Business address geocoding failed: %s", exc)
        return None


def _search_business_address(query: str) -> list[dict]:
    """Return Canadian address candidates for the Business Studio map picker.

    The result is deliberately a list instead of a single guess. The business
    owner must choose a candidate or move the map pin manually, so a geocoder
    can never silently save a nearby neighbourhood as the business location.
    """
    clean_query = " ".join(str(query or "").split()).strip()
    if len(clean_query) < 4:
        return []

    candidates: list[dict] = []
    seen: set[tuple[int, int]] = set()

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": clean_query,
                "format": "jsonv2",
                "limit": 5,
                "countrycodes": "ca",
                "addressdetails": 1,
                "dedupe": 1,
            },
            headers={
                "User-Agent": "AskMyCity/4.0 business-profile-map-picker",
                "Accept-Language": "en",
            },
            timeout=8,
        )
        response.raise_for_status()
        for item in response.json() or []:
            lat = float(item["lat"])
            lon = float(item["lon"])
            key = (round(lat * 100000), round(lon * 100000))
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "display_name": item.get("display_name") or clean_query,
                "latitude": lat,
                "longitude": lon,
                "source": "OpenStreetMap",
            })
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Nominatim address candidate search failed: %s", exc)

    # Photon gives a useful independent fallback when Nominatim cannot resolve a
    # newer building/address. We still restrict returned candidates to Canada.
    if len(candidates) < 3:
        try:
            response = requests.get(
                "https://photon.komoot.io/api/",
                params={"q": clean_query, "limit": 5, "lang": "en"},
                headers={"User-Agent": "AskMyCity/4.0 business-profile-map-picker"},
                timeout=8,
            )
            response.raise_for_status()
            for feature in (response.json() or {}).get("features", []):
                properties = feature.get("properties") or {}
                country_code = str(properties.get("countrycode") or "").lower()
                country = str(properties.get("country") or "").lower()
                if country_code not in {"ca", "can"} and "canada" not in country:
                    continue
                coordinates = (feature.get("geometry") or {}).get("coordinates") or []
                if len(coordinates) < 2:
                    continue
                lon, lat = float(coordinates[0]), float(coordinates[1])
                key = (round(lat * 100000), round(lon * 100000))
                if key in seen:
                    continue
                seen.add(key)
                label_parts = [
                    properties.get("housenumber"),
                    properties.get("street"),
                    properties.get("city") or properties.get("district"),
                    properties.get("state"),
                    properties.get("postcode"),
                    properties.get("country"),
                ]
                candidates.append({
                    "display_name": ", ".join(str(value) for value in label_parts if value),
                    "latitude": lat,
                    "longitude": lon,
                    "source": "Photon/OpenStreetMap",
                })
                if len(candidates) >= 5:
                    break
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning("Photon address candidate search failed: %s", exc)

    return candidates[:5]


def _profile_for_user(session: Session, user_id: int) -> BusinessProfile | None:
    return session.exec(
        select(BusinessProfile).where(BusinessProfile.owner_user_id == user_id)
    ).first()


def _profile_public(profile: BusinessProfile) -> BusinessProfilePublic:
    return BusinessProfilePublic.model_validate(profile)


def _completion(data: BusinessProfileUpdate) -> int:
    fields = [
        data.display_name,
        data.description,
        data.category,
        data.phone_number,
        data.website,
        data.email,
        data.full_address,
        data.city,
        data.hours_json,
        data.amenities_json,
        data.logo_url,
        data.cover_photo_url,
    ]
    completed = sum(bool(str(value).strip()) for value in fields if value is not None)
    total = len(fields)
    return max(10, min(100, round(completed / total * 100)))





def _merge_owner_amenities(existing_features_json: str | None, amenities_json: str | None) -> str | None:
    """Merge Business Studio owner-provided amenities into Place.features_json.

    Existing imported/enriched features are preserved. Owner-provided data is stored
    under the explicit `owner_provided` key so search can distinguish its source.
    """
    if not amenities_json:
        return existing_features_json
    try:
        owner_data = json.loads(amenities_json)
    except (TypeError, json.JSONDecodeError):
        return existing_features_json

    existing: dict = {}
    if existing_features_json:
        try:
            parsed = json.loads(existing_features_json)
            if isinstance(parsed, dict):
                existing = parsed
        except (TypeError, json.JSONDecodeError):
            existing = {}

    existing["owner_provided"] = {
        "source": "business_owner",
        "updated_at": utc_now().isoformat(),
        "data": owner_data,
    }
    return json.dumps(existing, ensure_ascii=False)


def _sync_profile_to_place(session: Session, profile: BusinessProfile) -> None:
    """Create or update the customer-facing Place row for a Business Studio profile."""
    place = session.get(Place, profile.place_id) if profile.place_id else None

    if place is None:
        place = Place(
            business_id=f"business-studio-{profile.id}",
            name=profile.display_name,
            category=profile.category or "business",
            source="business_studio",
        )

    previous_address = (
        place.full_address,
        place.city,
        place.postal_code,
    )
    new_address = (
        profile.full_address,
        profile.city,
        profile.postal_code,
    )

    place.name = profile.display_name
    place.category = profile.category or "business"
    place.business_type = profile.category or "business"
    place.description = profile.description
    place.phone_number = profile.phone_number
    place.website = profile.website
    place.full_address = profile.full_address
    place.city = profile.city
    place.postal_code = profile.postal_code

    address_changed = previous_address != new_address
    if address_changed or place.latitude is None or place.longitude is None:
        coordinates = _geocode_business_address(
            profile.full_address,
            profile.city,
            profile.postal_code,
        )
        if coordinates is not None:
            place.latitude, place.longitude = coordinates
        elif address_changed:
            # Never keep coordinates belonging to an old address.
            place.latitude = None
            place.longitude = None

    place.working_hours_json = profile.hours_json
    place.features_json = _merge_owner_amenities(place.features_json, profile.amenities_json)
    place.logo_url = profile.logo_url
    place.photo_url = profile.cover_photo_url or profile.logo_url
    place.source = "business_studio"
    place.business_status = "ACTIVE" if profile.is_published else "UNPUBLISHED"
    place.updated_at = utc_now()

    session.add(place)
    session.flush()
    profile.place_id = place.id
    session.add(profile)

def _require_business_user(user: User) -> None:
    if user.account_type not in {"business_owner", "independent_worker"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A business or independent professional account is required.",
        )


@router.get("/overview", response_model=DashboardOverview)
def overview(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    profile = _profile_for_user(session, current_user.id)
    claims = session.exec(
        select(BusinessClaim).where(BusinessClaim.user_id == current_user.id)
    ).all()
    menu_count = 0
    suggestions: list[str] = []
    if profile:
        menu_count = len(session.exec(
            select(MenuItem).where(MenuItem.business_profile_id == profile.id)
        ).all())
        if not profile.description:
            suggestions.append("Add a clear business description.")
        if not profile.hours_json:
            suggestions.append("Add your business hours.")
        if not profile.logo_url:
            suggestions.append("Upload your logo.")
        if menu_count == 0:
            suggestions.append("Add your first menu item or service.")
        if not profile.phone_number:
            suggestions.append("Add a phone number customers can use.")
    elif current_user.account_type in {"business_owner", "independent_worker"}:
        suggestions.append("Create or claim your business profile.")

    return DashboardOverview(
        account_type=current_user.account_type,
        profile=_profile_public(profile) if profile else None,
        pending_claims=sum(1 for claim in claims if claim.status == "pending"),
        menu_items=menu_count,
        suggestions=suggestions[:4],
    )


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _business_health(
    profile: BusinessProfile | None,
    menu_count: int,
    claim_count: int,
    metrics_by_label: dict[str, int],
    average_rating: float,
    review_count: int,
) -> tuple[int, list[HealthDimension]]:
    """Calculate business health only from real profile and engagement data."""
    completion = profile.profile_completion if profile else 0
    profile_views = metrics_by_label.get("Profile views", 0)
    total_clicks = sum(metrics_by_label.get(label, 0) for label in [
        "Menu views", "Direction requests", "Phone clicks", "Website clicks"
    ])
    favorites = metrics_by_label.get("Favorites", 0)

    visibility = _clamp(round(min(100, profile_views * 4 + menu_count * 5 + (15 if profile and profile.is_published else 0))))
    trust = _clamp(round(
        (average_rating / 5 * 55 if review_count else 0)
        + min(review_count * 5, 25)
        + (10 if profile and profile.phone_number else 0)
        + (10 if profile and profile.website else 0)
        + min(claim_count * 10, 10)
    ))
    freshness = 0
    if profile:
        age_days = max(0, (utc_now() - profile.updated_at).days)
        freshness = _clamp(100 - min(age_days * 2, 80))
        if not profile.hours_json:
            freshness = max(0, freshness - 20)
    engagement = _clamp(round(min(100, total_clicks * 7 + favorites * 8 + review_count * 10)))

    dimensions = [
        HealthDimension(label="Visibility", score=visibility),
        HealthDimension(label="Trust", score=trust),
        HealthDimension(label="Completeness", score=completion),
        HealthDimension(label="Freshness", score=freshness),
        HealthDimension(label="Engagement", score=engagement),
    ]
    return round(sum(item.score for item in dimensions) / len(dimensions)), dimensions


def _coach(
    profile: BusinessProfile | None,
    menu_count: int,
    metrics_by_label: dict[str, int],
    review_count: int,
    unanswered_reviews: int,
) -> CoachRecommendation:
    if not profile:
        return CoachRecommendation(title="Create your business identity", message="Customers need accurate business information before AskMyCity can recommend you.", action_label="Create profile", action_path="/dashboard/profile", impact="Unlock your public business page", priority="high")
    if not profile.is_published:
        return CoachRecommendation(title="Publish your business", message="Your profile is saved but customers cannot discover it until it is published.", action_label="Publish profile", action_path="/dashboard/profile", impact="Make your business searchable", priority="high")
    if unanswered_reviews > 0:
        return CoachRecommendation(title="Reply to your latest review", message=f"You have {unanswered_reviews} customer review{'s' if unanswered_reviews != 1 else ''} waiting for a response.", action_label="Open reviews", action_path="/dashboard/reviews", impact="Build customer trust", priority="high")
    if not profile.hours_json:
        return CoachRecommendation(title="Add your opening hours", message="Customers often search for businesses that are open now.", action_label="Add business hours", action_path="/dashboard/profile", impact="Improve search accuracy", priority="high")
    if menu_count == 0:
        return CoachRecommendation(title="Add your first menu item", message="Menu details help customers understand what you offer.", action_label="Open Menu Studio", action_path="/dashboard/menu", impact="Improve discovery", priority="high")
    if not profile.cover_photo_url:
        return CoachRecommendation(title="Add a cover photo", message="A cover photo makes your public page more complete and trustworthy.", action_label="Update business", action_path="/dashboard/profile", impact="Improve trust and engagement", priority="medium")
    if review_count == 0:
        return CoachRecommendation(title="Get your first customer review", message="Your profile is ready. Share your public page with a real customer and ask for honest feedback.", action_label="Preview page", action_path=f"/places/{profile.place_id}" if profile.place_id else "/", impact="Start building trust", priority="medium")
    if metrics_by_label.get("Profile views", 0) > 0 and sum(metrics_by_label.get(x, 0) for x in ["Phone clicks", "Website clicks", "Direction requests"]) == 0:
        return CoachRecommendation(title="Turn views into customer actions", message="Customers are viewing your profile but have not clicked your contact options yet. Check that your phone, website, and address are complete.", action_label="Edit business", action_path="/dashboard/profile", impact="Increase customer conversions", priority="medium")
    return CoachRecommendation(title="Keep your profile fresh", message="Your business has real customer activity. Keep your hours, photos, menu, and contact details up to date.", action_label="Review profile", action_path="/dashboard/profile", impact="Maintain customer confidence", priority="low")


@router.get("/studio-overview", response_model=BusinessStudioOverview)
def studio_overview(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    claims = session.exec(select(BusinessClaim).where(BusinessClaim.user_id == current_user.id)).all()
    menu_count = 0
    if profile:
        menu_count = len(session.exec(select(MenuItem).where(MenuItem.business_profile_id == profile.id)).all())

    now = utc_now()
    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)

    def change_percent(current: int, previous: int) -> int:
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100)

    metrics: list[StudioMetric] = []
    metrics_by_label: dict[str, int] = {}
    all_time_by_label: dict[str, int] = {}
    recent_reviews: list[Review] = []
    recent_favorites: list[Favorite] = []
    recent_events: list[BusinessEvent] = []
    average_rating = 0.0
    review_count = 0
    unanswered_reviews = 0

    if profile and profile.place_id:
        def event_count(event_type: str, start: datetime | None = None, end: datetime | None = None) -> int:
            statement = select(func.count(BusinessEvent.id)).where(
                BusinessEvent.place_id == profile.place_id,
                BusinessEvent.event_type == event_type,
            )
            if start is not None:
                statement = statement.where(BusinessEvent.created_at >= start)
            if end is not None:
                statement = statement.where(BusinessEvent.created_at < end)
            return int(session.exec(statement).one() or 0)

        def row_count(model, start: datetime | None = None, end: datetime | None = None) -> int:
            statement = select(func.count(model.id)).where(model.place_id == profile.place_id)
            if start is not None:
                statement = statement.where(model.created_at >= start)
            if end is not None:
                statement = statement.where(model.created_at < end)
            return int(session.exec(statement).one() or 0)

        definitions = [
            ("Profile views", "profile_view", None),
            ("Menu views", "menu_view", None),
            ("Direction requests", "direction_click", None),
            ("Phone clicks", "phone_click", None),
            ("Website clicks", "website_click", None),
            ("Favorites", None, Favorite),
            ("Reviews", None, Review),
        ]
        for label, event_type, model in definitions:
            if event_type:
                current = event_count(event_type, current_start)
                previous = event_count(event_type, previous_start, current_start)
                all_time = event_count(event_type)
            else:
                current = row_count(model, current_start)
                previous = row_count(model, previous_start, current_start)
                all_time = row_count(model)
            metrics.append(StudioMetric(label=label, value=current, change_percent=change_percent(current, previous)))
            metrics_by_label[label] = current
            all_time_by_label[label] = all_time

        rating_row = session.exec(
            select(func.avg(Review.rating), func.count(Review.id)).where(Review.place_id == profile.place_id)
        ).one()
        average_rating = round(float(rating_row[0] or 0), 1)
        review_count = int(rating_row[1] or 0)
        unanswered_reviews = int(session.exec(
            select(func.count(Review.id)).where(
                Review.place_id == profile.place_id,
                Review.owner_reply.is_(None),
            )
        ).one() or 0)

        recent_reviews = session.exec(select(Review).where(Review.place_id == profile.place_id).order_by(Review.created_at.desc()).limit(5)).all()
        recent_favorites = session.exec(select(Favorite).where(Favorite.place_id == profile.place_id).order_by(Favorite.created_at.desc()).limit(5)).all()
        recent_events = session.exec(select(BusinessEvent).where(BusinessEvent.place_id == profile.place_id).order_by(BusinessEvent.created_at.desc()).limit(10)).all()
    else:
        for label in ["Profile views", "Menu views", "Direction requests", "Phone clicks", "Website clicks", "Favorites", "Reviews"]:
            metrics.append(StudioMetric(label=label, value=0, change_percent=0))
            metrics_by_label[label] = 0
            all_time_by_label[label] = 0

    health_score, dimensions = _business_health(profile, menu_count, len(claims), all_time_by_label, average_rating, review_count)
    status_label = "Excellent" if health_score >= 85 else "Strong" if health_score >= 70 else "Building" if health_score >= 45 else "Getting started"
    completion = profile.profile_completion if profile else 0

    activities: list[ActivityItem] = []
    for review in recent_reviews:
        activities.append(ActivityItem(type="review", title="New customer review", detail=f"A customer left a {review.rating}-star review.", occurred_at=review.created_at))
    for favorite in recent_favorites:
        activities.append(ActivityItem(type="favorite", title="Business saved", detail="A customer added your business to Favorites.", occurred_at=favorite.created_at))
    event_titles = {
        "profile_view": ("profile", "Public page viewed", "A customer opened your public business page."),
        "menu_view": ("menu", "Menu viewed", "A customer explored your menu."),
        "phone_click": ("phone", "Phone clicked", "A customer clicked your phone number."),
        "direction_click": ("direction", "Directions requested", "A customer opened directions."),
        "website_click": ("website", "Website visited", "A customer clicked your website."),
    }
    for event in recent_events:
        event_type, title, detail = event_titles.get(event.event_type, ("profile", "Customer activity", event.event_type))
        activities.append(ActivityItem(type=event_type, title=title, detail=detail, occurred_at=event.created_at))
    activities = sorted(activities, key=lambda item: item.occurred_at, reverse=True)[:10]
    if not activities:
        if profile and profile.is_published:
            activities.append(ActivityItem(type="tip", title="Waiting for your first customer activity", detail="Open your public page from a different account to test real views, favorites, clicks, and reviews.", occurred_at=profile.updated_at))
        else:
            activities.append(ActivityItem(type="tip", title="Publish your business", detail="Publish your profile before customers can interact with it.", occurred_at=now))

    return BusinessStudioOverview(
        place_id=profile.place_id if profile else None,
        business_name=profile.display_name if profile else current_user.name,
        business_category=profile.category if profile else "Local business",
        average_rating=average_rating,
        review_count=review_count,
        is_published=bool(profile and profile.is_published),
        health_score=health_score,
        health_status=status_label,
        health_dimensions=dimensions,
        metrics=metrics,
        coach=_coach(profile, menu_count, all_time_by_label, review_count, unanswered_reviews),
        activity=activities,
        profile_completion=completion,
        menu_items=menu_count,
        pending_claims=sum(1 for claim in claims if claim.status == "pending"),
    )


@router.post("/claims", response_model=BusinessClaimPublic, status_code=201)
def create_claim(
    payload: BusinessClaimCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    place = session.get(Place, payload.place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Business not found.")
    existing = session.exec(
        select(BusinessClaim).where(
            BusinessClaim.user_id == current_user.id,
            BusinessClaim.place_id == payload.place_id,
            BusinessClaim.status.in_(["pending", "approved"]),
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You already have an active claim for this business.")
    claim = BusinessClaim(
        user_id=current_user.id,
        place_id=payload.place_id,
        verification_method=payload.verification_method,
        verification_note=payload.verification_note,
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return BusinessClaimPublic(
        id=claim.id,
        place_id=claim.place_id,
        business_name=place.name,
        status=claim.status,
        verification_method=claim.verification_method,
        created_at=claim.created_at,
    )


@router.get("/claims", response_model=list[BusinessClaimPublic])
def list_claims(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    claims = session.exec(
        select(BusinessClaim).where(BusinessClaim.user_id == current_user.id)
    ).all()
    result = []
    for claim in claims:
        place = session.get(Place, claim.place_id)
        result.append(BusinessClaimPublic(
            id=claim.id,
            place_id=claim.place_id,
            business_name=place.name if place else "Unknown business",
            status=claim.status,
            verification_method=claim.verification_method,
            created_at=claim.created_at,
        ))
    return result


@router.get("/profile", response_model=BusinessProfilePublic | None)
def get_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    return _profile_public(profile) if profile else None



@router.get("/profile/geocode")
def search_profile_address(
    q: str = Query(min_length=4, max_length=500),
    current_user: User = Depends(get_current_user),
):
    _require_business_user(current_user)
    return _search_business_address(q)


@router.get("/profile/location", response_model=BusinessLocationPublic | None)
def get_profile_location(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    if not profile or not profile.place_id:
        return None
    place = session.get(Place, profile.place_id)
    if not place or place.latitude is None or place.longitude is None:
        return None
    return BusinessLocationPublic(
        place_id=place.id,
        latitude=place.latitude,
        longitude=place.longitude,
    )


@router.put("/profile/location", response_model=BusinessLocationPublic)
def save_profile_location(
    payload: BusinessLocationUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    if not profile or not profile.place_id:
        raise HTTPException(status_code=409, detail="Save your business profile before confirming its map location.")
    place = session.get(Place, profile.place_id)
    if not place:
        raise HTTPException(status_code=404, detail="The customer-facing business record was not found.")
    place.latitude = payload.latitude
    place.longitude = payload.longitude
    # Directions should always use the owner-confirmed pin instead of an old
    # imported/geocoded URL. This also keeps the public page consistent with
    # the coordinates used by the near-me search.
    place.google_maps_url = (
        "https://www.google.com/maps/dir/?api=1&destination="
        f"{payload.latitude:.7f},{payload.longitude:.7f}"
    )
    place.updated_at = utc_now()
    session.add(place)
    session.commit()
    session.refresh(place)
    return BusinessLocationPublic(
        place_id=place.id,
        latitude=place.latitude,
        longitude=place.longitude,
    )


@router.put("/profile", response_model=BusinessProfilePublic)
def save_profile(
    payload: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    if payload.hours_json:
        try:
            json.loads(payload.hours_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Business hours must be valid JSON.") from exc
    if payload.amenities_json:
        try:
            parsed_amenities = json.loads(payload.amenities_json)
            if not isinstance(parsed_amenities, dict):
                raise ValueError("Amenities must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Amenities and services must be valid JSON.") from exc
    profile = _profile_for_user(session, current_user.id)
    values = payload.model_dump()
    if profile is None:
        profile = BusinessProfile(owner_user_id=current_user.id, **values)
    else:
        for key, value in values.items():
            setattr(profile, key, value)
    profile.profile_completion = _completion(payload)
    profile.updated_at = utc_now()
    session.add(profile)
    session.flush()
    _sync_profile_to_place(session, profile)
    session.commit()
    session.refresh(profile)
    return _profile_public(profile)


@router.get("/menu", response_model=list[MenuItemPublic])
def list_menu(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    if not profile:
        return []
    return session.exec(
        select(MenuItem).where(MenuItem.business_profile_id == profile.id).order_by(MenuItem.category, MenuItem.name)
    ).all()


@router.post("/menu", response_model=MenuItemPublic, status_code=201)
def create_menu_item(
    payload: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=409, detail="Create your business profile first.")
    data = payload.model_dump()
    data["icon"] = data.get("icon") or infer_menu_icon(data.get("name"), data.get("category"), data.get("description"))
    item = MenuItem(business_profile_id=profile.id, **data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/menu/{item_id}", response_model=MenuItemPublic)
def update_menu_item(
    item_id: int,
    payload: MenuItemUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    item = session.get(MenuItem, item_id)
    if not profile or not item or item.business_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    data = payload.model_dump()
    data["icon"] = data.get("icon") or infer_menu_icon(data.get("name"), data.get("category"), data.get("description"))
    for key, value in data.items():
        setattr(item, key, value)
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/menu/{item_id}", status_code=204)
def delete_menu_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    item = session.get(MenuItem, item_id)
    if not profile or not item or item.business_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    session.delete(item)
    session.commit()
