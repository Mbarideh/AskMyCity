from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, or_
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_user
from models import Favorite, Place, User


router = APIRouter(
    prefix="/favorites",
    tags=["Favorites"],
)


def get_visible_place(session: Session, place_id: int) -> Place:
    place = session.get(Place, place_id)

    if (
        place is None
        or (
            place.source == "business_studio"
            and place.business_status != "ACTIVE"
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return place


@router.get("", response_model=list[Place])
def list_favorites(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    statement = (
        select(Place)
        .join(Favorite, Favorite.place_id == Place.id)
        .where(
            Favorite.user_id == current_user.id,
            or_(
                Place.source != "business_studio",
                and_(
                    Place.source == "business_studio",
                    Place.business_status == "ACTIVE",
                ),
            ),
        )
        .order_by(Favorite.created_at.desc())
    )

    return session.exec(statement).all()


@router.post(
    "/{place_id}",
    response_model=Place,
    status_code=status.HTTP_201_CREATED,
)
def add_favorite(
    place_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    place = get_visible_place(session, place_id)

    existing = session.exec(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.place_id == place_id,
        )
    ).first()

    if existing is None:
        favorite = Favorite(
            user_id=current_user.id,
            place_id=place_id,
        )
        session.add(favorite)
        session.commit()

    return place


@router.delete(
    "/{place_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_favorite(
    place_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    favorite = session.exec(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.place_id == place_id,
        )
    ).first()

    if favorite is not None:
        session.delete(favorite)
        session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
