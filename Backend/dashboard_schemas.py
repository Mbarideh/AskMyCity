from datetime import datetime
from sqlmodel import Field, SQLModel


class BusinessClaimCreate(SQLModel):
    place_id: int
    verification_method: str = Field(default="manual", max_length=30)
    verification_note: str | None = Field(default=None, max_length=1000)


class BusinessClaimPublic(SQLModel):
    id: int
    place_id: int
    business_name: str
    status: str
    verification_method: str
    created_at: datetime


class BusinessProfileUpdate(SQLModel):
    display_name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    category: str = Field(default="business", max_length=100)
    phone_number: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    full_address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    hours_json: str | None = None
    amenities_json: str | None = None
    logo_url: str | None = Field(default=None, max_length=1000)
    cover_photo_url: str | None = Field(default=None, max_length=1000)
    is_published: bool = False


class BusinessProfilePublic(BusinessProfileUpdate):
    id: int
    owner_user_id: int
    place_id: int | None
    profile_completion: int
    created_at: datetime
    updated_at: datetime


class BusinessLocationUpdate(SQLModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BusinessLocationPublic(BusinessLocationUpdate):
    place_id: int


class MenuItemCreate(SQLModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="Other", max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    price: float | None = Field(default=None, ge=0)
    photo_url: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=16)
    is_available: bool = True
    is_featured: bool = False


class MenuItemUpdate(MenuItemCreate):
    pass


class MenuItemPublic(MenuItemCreate):
    id: int
    business_profile_id: int
    created_at: datetime
    updated_at: datetime


class DashboardOverview(SQLModel):
    account_type: str
    profile: BusinessProfilePublic | None = None
    pending_claims: int = 0
    menu_items: int = 0
    profile_views: int = 0
    direction_requests: int = 0
    phone_clicks: int = 0
    new_reviews: int = 0
    suggestions: list[str] = Field(default_factory=list)


class HealthDimension(SQLModel):
    label: str
    score: int = Field(ge=0, le=100)


class StudioMetric(SQLModel):
    label: str
    value: int
    change_percent: int = 0


class CoachRecommendation(SQLModel):
    title: str
    message: str
    action_label: str
    action_path: str
    impact: str
    priority: str = "medium"


class ActivityItem(SQLModel):
    type: str
    title: str
    detail: str
    occurred_at: datetime


class BusinessStudioOverview(SQLModel):
    place_id: int | None = None
    business_name: str
    average_rating: float = 0
    review_count: int = 0
    business_category: str
    is_published: bool
    health_score: int = Field(ge=0, le=100)
    health_status: str
    health_dimensions: list[HealthDimension]
    metrics: list[StudioMetric]
    coach: CoachRecommendation
    activity: list[ActivityItem]
    profile_completion: int
    menu_items: int
    pending_claims: int
