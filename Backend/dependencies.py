from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlmodel import Session

from auth import decode_access_token
from database import engine
from models import User
from schemas import UserPublic


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def create_public_user(
    user: User,
) -> UserPublic:
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The user account has no ID.",
        )

    return UserPublic(
        id=user.id,
        name=user.name,
        email=user.email,
        account_type=user.account_type,
        business_name=user.business_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must log in first.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    user_id = decode_access_token(
        credentials.credentials
    )

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    try:
        numeric_user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login token.",
        )

    with Session(engine) as session:
        user = session.get(
            User,
            numeric_user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive.",
            )

        session.expunge(user)

        return user