from datetime import datetime
from typing import Literal

from sqlmodel import Field, SQLModel

from models import Place, ProviderBase


class ProviderCreate(ProviderBase):
    pass


class UserRegister(SQLModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    email: str = Field(
        min_length=5,
        max_length=255,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    account_type: str = Field(
        default="customer",
        max_length=30,
    )

    business_name: str | None = Field(
        default=None,
        max_length=200,
    )


class UserLogin(SQLModel):
    email: str = Field(
        min_length=5,
        max_length=255,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserPublic(SQLModel):
    id: int
    name: str
    email: str
    account_type: str
    business_name: str | None
    is_active: bool
    created_at: datetime


class TokenResponse(SQLModel):
    access_token: str
    token_type: str
    user: UserPublic


class AIConversationMessage(SQLModel):
    """
    One message from the current AI conversation.

    The frontend sends recent messages with every
    AI request so the backend can understand follow-up
    instructions.
    """

    role: Literal[
        "user",
        "assistant",
    ]

    content: str = Field(
        min_length=1,
        max_length=2000,
    )

    # IDs of result cards attached to an assistant turn.  The frontend sends
    # these back on follow-up messages so conversational operations (
    # "find more", "which one is closest?", etc.) can operate on the exact
    # previously displayed set instead of re-running a broad search.
    result_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
    )


class AISearchRequest(SQLModel):
    """
    A new AI search request.

    messages contains the recent conversation history.
    The current query remains separate so the endpoint
    stays compatible with the existing search workflow.
    """

    query: str = Field(
        min_length=3,
        max_length=1000,
    )

    messages: list[AIConversationMessage] = Field(
        default_factory=list,
        max_length=20,
    )

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )


class AISearchFilters(SQLModel):
    category: str | None = None
    city: str | None = None
    search: str | None = None
    requested_cuisine: str | None = None
    requested_dishes: list[str] = Field(default_factory=list)
    budget_preference: str | None = None
    maximum_price: float | None = Field(default=None, ge=0)
    atmosphere: list[str] = Field(default_factory=list)
    dietary_options: list[str] = Field(default_factory=list)
    # Saved business amenities/services that must be explicitly confirmed,
    # for example family-friendly, parking, patio, dine-in, or delivery.
    requested_features: list[str] = Field(default_factory=list)
    open_now: bool | None = None
    language: str | None = None
    context_mode: str = "standalone"
    minimum_rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
    )
    minimum_review_count: int | None = Field(
        default=None,
        ge=0,
    )
    urgency: str | None = None
    explanation: str | None = None


class PlaceResult(SQLModel):
    id: int
    business_id: str
    place_id: str | None
    name: str
    category: str
    full_address: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    rating: float | None
    review_count: int | None
    phone_number: str | None
    website: str | None
    google_maps_url: str | None
    photo_url: str | None
    logo_url: str | None
    street_view_url: str | None
    business_type: str | None
    subtypes: str | None
    price_range: str | None
    working_hours_json: str | None
    features_json: str | None
    verified: bool
    description: str | None
    distance_km: float | None = None
    match_score: int | None = None
    match_reasons: list[str] = Field(default_factory=list)
    confidence: str | None = None
    enrichment_status: str = "not_enriched"
    ai_summary: str | None = None


class AISearchResponse(SQLModel):
    """
    AI search response returned to the frontend.

    assistant_message is displayed inside the chat.
    It also becomes part of the next request's
    conversation history.
    """

    query: str
    assistant_message: str
    filters: AISearchFilters
    results: list[PlaceResult]
    decision_trace: dict | None = None
