from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import func
from sqlmodel import Session, select

from database import get_session
from models import Provider
from schemas import ProviderCreate


router = APIRouter(
    prefix="/providers",
    tags=["Providers"],
)


@router.get(
    "",
    response_model=list[Provider],
)
def get_providers(
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    language: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    statement = select(Provider)

    if city:
        statement = statement.where(
            func.lower(Provider.city)
            == city.strip().lower()
        )

    if category:
        statement = statement.where(
            func.lower(Provider.category)
            == category.strip().lower()
        )

    if language:
        statement = statement.where(
            func.lower(Provider.language)
            == language.strip().lower()
        )

    return session.exec(statement).all()


@router.post(
    "",
    response_model=Provider,
    status_code=status.HTTP_201_CREATED,
)
def create_provider(
    provider_data: ProviderCreate,
    session: Session = Depends(get_session),
):
    provider = Provider.model_validate(
        provider_data
    )

    session.add(provider)
    session.commit()
    session.refresh(provider)

    return provider


@router.get(
    "/{provider_id}",
    response_model=Provider,
)
def get_provider(
    provider_id: int,
    session: Session = Depends(get_session),
):
    provider = session.get(
        Provider,
        provider_id,
    )

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    return provider


@router.put(
    "/{provider_id}",
    response_model=Provider,
)
def update_provider(
    provider_id: int,
    provider_data: ProviderCreate,
    session: Session = Depends(get_session),
):
    provider = session.get(
        Provider,
        provider_id,
    )

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    provider.name = provider_data.name
    provider.category = provider_data.category
    provider.city = provider_data.city
    provider.language = provider_data.language

    session.add(provider)
    session.commit()
    session.refresh(provider)

    return provider


@router.delete(
    "/{provider_id}",
)
def delete_provider(
    provider_id: int,
    session: Session = Depends(get_session),
):
    provider = session.get(
        Provider,
        provider_id,
    )

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    session.delete(provider)
    session.commit()

    return {
        "message": (
            "Provider deleted successfully."
        )
    }