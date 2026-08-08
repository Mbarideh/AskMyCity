from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProviderBase(SQLModel):
    name: str
    category: str
    city: str
    language: str


class Provider(ProviderBase, table=True):
    __tablename__ = "providers"
    id: int | None = Field(default=None, primary_key=True)


class Place(SQLModel, table=True):
    __tablename__ = "places"

    id: int | None = Field(default=None, primary_key=True)
    business_id: str = Field(index=True, unique=True)
    place_id: str | None = Field(default=None, index=True)
    google_id: str | None = Field(default=None, index=True)
    cid: str | None = Field(default=None, index=True)

    name: str
    category: str = Field(default="business", index=True)
    business_type: str | None = Field(default=None, index=True)
    subtypes: str | None = None

    full_address: str | None = None
    street: str | None = None
    city: str | None = Field(default=None, index=True)
    county: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    time_zone: str | None = None

    rating: float | None = None
    review_count: int | None = None
    reviews_1_star: int | None = None
    reviews_2_star: int | None = None
    reviews_3_star: int | None = None
    reviews_4_star: int | None = None
    reviews_5_star: int | None = None
    reviews_link: str | None = None

    phone_number: str | None = None
    website: str | None = None
    google_maps_url: str | None = None
    photo_url: str | None = None
    logo_url: str | None = None
    street_view_url: str | None = None

    business_status: str | None = None
    price_range: str | None = None
    working_hours_json: str | None = None
    other_hours_json: str | None = None
    features_json: str | None = None
    reservation_links: str | None = None
    menu_link: str | None = None
    order_links: str | None = None

    verified: bool = Field(default=False)
    description: str | None = None
    source: str = Field(default="manual", index=True)
    source_query: str | None = None
    imported_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BusinessAIProfile(SQLModel, table=True):
    """AI-generated knowledge kept separate from trusted source data."""

    __tablename__ = "business_ai_profiles"

    id: int | None = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="places.id", unique=True, index=True)
    ai_summary: str | None = None
    cuisine_types_json: str | None = None
    cuisine_confidence: str = Field(default="low", index=True)
    menu_items_json: str | None = None
    menu_confidence: str = Field(default="low", index=True)
    signature_items_json: str | None = None
    dish_reputation_json: str | None = None
    price_level: str | None = Field(default=None, index=True)
    average_main_price_cad: float | None = None
    price_confidence: str = Field(default="low", index=True)
    value_for_money: str | None = Field(default=None, index=True)
    best_for_json: str | None = None
    atmosphere_json: str | None = None
    dietary_options_json: str | None = None
    service_features_json: str | None = None
    search_tags_json: str | None = None
    evidence_summary: str | None = None
    confidence: str = Field(default="low", index=True)
    source_urls_json: str | None = None
    enrichment_mode: str = Field(default="dataset", index=True)
    model_name: str | None = None
    prompt_version: str = Field(default="v2-evidence")
    enriched_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BusinessResearchCache(SQLModel, table=True):
    """Persistent record of a targeted web-research attempt.

    This prevents AskMyCity from paying for the same business + request twice,
    including negative findings such as "gnocchi not verified".
    """

    __tablename__ = "business_research_cache"

    id: int | None = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    target_key: str = Field(index=True, max_length=500)
    requested_cuisine: str | None = Field(default=None, max_length=100)
    requested_dishes_json: str | None = None
    maximum_price: float | None = None
    status: str = Field(default="completed", index=True, max_length=30)
    matched: bool = Field(default=False, index=True)
    error_message: str | None = None
    researched_at: datetime = Field(default_factory=utc_now, index=True)



class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batches"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    source_file: str | None = None
    city: str | None = Field(default=None, index=True)
    category: str | None = Field(default=None, index=True)
    status: str = Field(default="completed", index=True)
    imported_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    is_paid_api_request: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    account_type: str = Field(default="customer", max_length=30, index=True)
    business_name: str | None = Field(default=None, max_length=200)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class Favorite(SQLModel, table=True):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "place_id",
            name="uq_favorites_user_place",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class BusinessEvent(SQLModel, table=True):
    __tablename__ = "business_events"

    id: int | None = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    event_type: str = Field(index=True, max_length=50)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeResearchJob(SQLModel, table=True):
    """Durable, cost-controlled research queue for the knowledge builder."""

    __tablename__ = "knowledge_research_jobs"

    id: int | None = Field(default=None, primary_key=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    target_key: str = Field(index=True, max_length=500)
    requested_cuisine: str | None = Field(default=None, max_length=100)
    requested_dishes_json: str | None = None
    maximum_price: float | None = None
    priority: int = Field(default=100, index=True)
    reason: str = Field(default="knowledge_builder", index=True, max_length=100)
    status: str = Field(default="queued", index=True, max_length=30)
    matched: bool = Field(default=False, index=True)
    attempt_count: int = 0
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class BusinessClaim(SQLModel, table=True):
    __tablename__ = "business_claims"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    status: str = Field(default="pending", index=True, max_length=30)
    verification_method: str = Field(default="manual", max_length=30)
    verification_note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_at: datetime | None = None


class BusinessProfile(SQLModel, table=True):
    __tablename__ = "business_profiles"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    place_id: int | None = Field(default=None, foreign_key="places.id", unique=True, index=True)
    display_name: str
    description: str | None = None
    category: str = Field(default="business", index=True)
    phone_number: str | None = None
    website: str | None = None
    email: str | None = None
    full_address: str | None = None
    city: str | None = Field(default=None, index=True)
    postal_code: str | None = None
    hours_json: str | None = None
    amenities_json: str | None = None
    logo_url: str | None = None
    cover_photo_url: str | None = None
    is_published: bool = Field(default=False, index=True)
    profile_completion: int = Field(default=20, ge=0, le=100)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"

    id: int | None = Field(default=None, primary_key=True)
    business_profile_id: int = Field(foreign_key="business_profiles.id", index=True)
    name: str
    category: str = Field(default="Other", index=True)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    photo_url: str | None = None
    icon: str | None = Field(default=None, max_length=16)
    is_available: bool = Field(default=True, index=True)
    is_featured: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    place_id: int = Field(foreign_key="places.id", index=True)
    rating: int = Field(ge=1, le=5, index=True)
    comment: str | None = None
    owner_reply: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BusinessMedia(SQLModel, table=True):
    __tablename__ = "business_media"

    id: int | None = Field(default=None, primary_key=True)
    business_profile_id: int = Field(foreign_key="business_profiles.id", index=True)
    media_type: str = Field(index=True, max_length=20)  # logo, cover, gallery
    file_url: str = Field(max_length=1000)
    original_name: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
