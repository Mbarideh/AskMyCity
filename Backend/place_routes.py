from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from database import get_session
from models import Place


router = APIRouter(
    prefix="/places",
    tags=["Places"],
)


def searchable_places_statement():
    """Return only records allowed on public customer pages."""
    inactive_statuses = (
        "CLOSED",
        "CLOSED_PERMANENTLY",
        "PERMANENTLY_CLOSED",
        "INACTIVE",
        "UNPUBLISHED",
    )

    return select(Place).where(
        or_(
            and_(
                Place.source == "business_studio",
                Place.business_status == "ACTIVE",
            ),
            and_(
                Place.source != "business_studio",
                or_(
                    Place.business_status.is_(None),
                    func.upper(Place.business_status).notin_(inactive_statuses),
                ),
            ),
        )
    )


@router.get(
    "",
    response_model=list[Place],
)
def get_places(
    search: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    minimum_rating: float | None = Query(
        default=None,
        ge=0,
        le=5,
    ),
    session: Session = Depends(get_session),
):
    statement = searchable_places_statement()

    if search:
        search_value = (
            f"%{search.strip()}%"
        )

        statement = statement.where(
            or_(
                Place.name.ilike(search_value),
                Place.city.ilike(search_value),
                Place.category.ilike(search_value),
                Place.full_address.ilike(search_value),
            )
        )

    if city:
        statement = statement.where(
            func.lower(Place.city)
            == city.strip().lower()
        )

    if category:
        statement = statement.where(
            func.lower(Place.category)
            == category.strip().lower()
        )

    if minimum_rating is not None:
        statement = statement.where(
            Place.rating >= minimum_rating
        )

    statement = statement.order_by(
        Place.rating.desc().nullslast(),
        Place.review_count.desc().nullslast(),
    )

    return session.exec(statement).all()


@router.get(
    "/explore",
    response_model=list[Place],
)
def explore_places(
    search: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
    session: Session = Depends(get_session),
):
    statement = searchable_places_statement()

    if search:
        search_value = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Place.name.ilike(search_value),
                Place.category.ilike(search_value),
                Place.business_type.ilike(search_value),
                Place.city.ilike(search_value),
                Place.full_address.ilike(search_value),
                Place.description.ilike(search_value),
            )
        )

    if city:
        statement = statement.where(
            func.lower(Place.city) == city.strip().lower()
        )

    if category:
        statement = statement.where(
            func.lower(Place.category) == category.strip().lower()
        )

    statement = statement.order_by(
        Place.verified.desc(),
        Place.rating.desc().nullslast(),
        Place.review_count.desc().nullslast(),
        Place.name.asc(),
    ).limit(limit)

    return session.exec(statement).all()


@router.get(
    "/{place_id}",
    response_model=Place,
)
def get_place(
    place_id: int,
    session: Session = Depends(get_session),
):
    place = session.get(
        Place,
        place_id,
    )

    if (
        place is None
        or (
            place.source == "business_studio"
            and place.business_status != "ACTIVE"
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found.",
        )

    return place