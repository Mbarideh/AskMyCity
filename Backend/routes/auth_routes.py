from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import func
from sqlmodel import Session, select

from auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from database import get_session
from dependencies import (
    create_public_user,
    get_current_user,
)
from models import User
from schemas import (
    TokenResponse,
    UserLogin,
    UserPublic,
    UserRegister,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

ALLOWED_ACCOUNT_TYPES = {
    "customer",
    "business_owner",
    "independent_worker",
}


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserRegister,
    session: Session = Depends(get_session),
):
    normalized_name = user_data.name.strip()
    normalized_email = user_data.email.strip().lower()
    normalized_account_type = (
        user_data.account_type.strip().lower()
    )

    normalized_business_name = (
        user_data.business_name.strip()
        if user_data.business_name
        else None
    )

    if normalized_account_type not in ALLOWED_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Account type must be customer, "
                "business_owner, or independent_worker."
            ),
        )

    if (
        normalized_account_type == "business_owner"
        and not normalized_business_name
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Business name is required.",
        )

    existing_user = session.exec(
        select(User).where(
            func.lower(User.email)
            == normalized_email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this email "
                "already exists."
            ),
        )

    new_user = User(
        name=normalized_name,
        email=normalized_email,
        hashed_password=hash_password(
            user_data.password
        ),
        account_type=normalized_account_type,
        business_name=normalized_business_name,
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return create_public_user(new_user)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    login_data: UserLogin,
    session: Session = Depends(get_session),
):
    normalized_email = (
        login_data.email.strip().lower()
    )

    user = session.exec(
        select(User).where(
            func.lower(User.email)
            == normalized_email
        )
    ).first()

    if (
        user is None
        or not verify_password(
            login_data.password,
            user.hashed_password,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    access_token = create_access_token(
        subject=user.id
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=create_public_user(user),
    )


@router.get(
    "/me",
    response_model=UserPublic,
)
def get_my_account(
    current_user: User = Depends(
        get_current_user
    ),
):
    return create_public_user(
        current_user
    )