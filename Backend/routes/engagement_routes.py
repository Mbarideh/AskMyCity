from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_user
from models import (
    BusinessEvent,
    BusinessProfile,
    MenuItem,
    Place,
    Review,
    User,
    utc_now,
)

router = APIRouter(tags=["Engagement"])

ALLOWED_EVENTS = {
    "profile_view",
    "menu_view",
    "phone_click",
    "direction_click",
    "website_click",
}


class EventCreate(BaseModel):
    event_type: str


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=3000)


class ReviewReply(BaseModel):
    owner_reply: str | None = Field(default=None, max_length=3000)


class ReviewPublic(BaseModel):
    id: int
    user_id: int
    user_name: str
    place_id: int
    rating: int
    comment: str | None
    owner_reply: str | None
    created_at: datetime
    updated_at: datetime


class PublicMenuItem(BaseModel):
    id: int
    name: str
    category: str
    description: str | None
    price: float | None
    photo_url: str | None
    icon: str | None = None
    is_featured: bool


def _review_public(session: Session, review: Review) -> ReviewPublic:
    user = session.get(User, review.user_id)
    return ReviewPublic(
        id=review.id,
        user_id=review.user_id,
        user_name=user.name if user else "Customer",
        place_id=review.place_id,
        rating=review.rating,
        comment=review.comment,
        owner_reply=review.owner_reply,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _owned_profile(session: Session, user_id: int) -> BusinessProfile:
    profile = session.exec(
        select(BusinessProfile).where(BusinessProfile.owner_user_id == user_id)
    ).first()
    if not profile or not profile.place_id:
        raise HTTPException(status_code=404, detail="No connected business profile was found.")
    return profile


@router.get("/places/{place_id}/reviews", response_model=list[ReviewPublic])
def list_reviews(place_id: int, session: Session = Depends(get_session)):
    if not session.get(Place, place_id):
        raise HTTPException(status_code=404, detail="Business not found.")
    rows = session.exec(
        select(Review)
        .where(Review.place_id == place_id)
        .order_by(Review.created_at.desc())
    ).all()
    return [_review_public(session, row) for row in rows]


@router.post(
    "/places/{place_id}/reviews",
    response_model=ReviewPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    place_id: int,
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    place = session.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Business not found.")

    existing = session.exec(
        select(Review).where(
            Review.user_id == current_user.id,
            Review.place_id == place_id,
        )
    ).first()

    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment.strip() if payload.comment else None
        existing.updated_at = utc_now()
        review = existing
    else:
        review = Review(
            user_id=current_user.id,
            place_id=place_id,
            rating=payload.rating,
            comment=payload.comment.strip() if payload.comment else None,
        )

    session.add(review)
    session.commit()
    session.refresh(review)

    # Keep imported/public rating data separate from AskMyCity community reviews.
    # Previously a single local review overwrote the Google/imported rating and
    # review_count stored on Place, which made business cards suddenly show only
    # the AskMyCity review count. Community review aggregates are calculated from
    # the Review table by the frontend instead.
    return _review_public(session, review)


@router.get("/places/{place_id}/menu", response_model=list[PublicMenuItem])
def public_menu(place_id: int, session: Session = Depends(get_session)):
    profile = session.exec(
        select(BusinessProfile).where(BusinessProfile.place_id == place_id)
    ).first()
    if not profile:
        return []
    items = session.exec(
        select(MenuItem)
        .where(
            MenuItem.business_profile_id == profile.id,
            MenuItem.is_available == True,  # noqa: E712
        )
        .order_by(MenuItem.is_featured.desc(), MenuItem.created_at.desc())
    ).all()
    return [
        PublicMenuItem(
            id=item.id,
            name=item.name,
            category=item.category,
            description=item.description,
            price=item.price,
            photo_url=item.photo_url,
            icon=item.icon,
            is_featured=item.is_featured,
        )
        for item in items
    ]


@router.post("/places/{place_id}/events", status_code=status.HTTP_201_CREATED)
def record_event(
    place_id: int,
    payload: EventCreate,
    session: Session = Depends(get_session),
):
    if payload.event_type not in ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail="Unsupported event type.")
    if not session.get(Place, place_id):
        raise HTTPException(status_code=404, detail="Business not found.")
    event = BusinessEvent(place_id=place_id, event_type=payload.event_type)
    session.add(event)
    session.commit()
    session.refresh(event)
    total = int(session.exec(
        select(func.count(BusinessEvent.id)).where(
            BusinessEvent.place_id == place_id,
            BusinessEvent.event_type == payload.event_type,
        )
    ).one() or 0)
    return {"recorded": True, "event_id": event.id, "total": total}


@router.get("/dashboard/reviews-data", response_model=list[ReviewPublic])
def business_reviews(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    profile = _owned_profile(session, current_user.id)
    rows = session.exec(
        select(Review)
        .where(Review.place_id == profile.place_id)
        .order_by(Review.created_at.desc())
    ).all()
    return [_review_public(session, row) for row in rows]


@router.patch("/dashboard/reviews/{review_id}/reply", response_model=ReviewPublic)
def reply_to_review(
    review_id: int,
    payload: ReviewReply,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    profile = _owned_profile(session, current_user.id)
    review = session.get(Review, review_id)
    if not review or review.place_id != profile.place_id:
        raise HTTPException(status_code=404, detail="Review not found.")
    review.owner_reply = payload.owner_reply.strip() if payload.owner_reply else None
    review.updated_at = utc_now()
    session.add(review)
    session.commit()
    session.refresh(review)
    return _review_public(session, review)
