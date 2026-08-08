from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_user
from models import BusinessProfile, MenuItem, User, utc_now

router = APIRouter(prefix="/dashboard/menu", tags=["Menu item images"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "menu-items"
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_FILE_SIZE = 8 * 1024 * 1024


def _owned_profile(session: Session, user: User) -> BusinessProfile:
    profile = session.exec(
        select(BusinessProfile).where(BusinessProfile.owner_user_id == user.id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your business profile first.")
    return profile


def _owned_item(session: Session, user: User, item_id: int) -> MenuItem:
    profile = _owned_profile(session, user)
    item = session.get(MenuItem, item_id)
    if not item or item.business_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    return item


def _delete_local_file(file_url: str | None) -> None:
    if not file_url or not file_url.startswith("/media/"):
        return
    media_root = Path(__file__).resolve().parent.parent / "uploads"
    file_path = media_root / file_url.removeprefix("/media/")
    file_path.unlink(missing_ok=True)


@router.post("/{item_id}/image")
async def upload_menu_item_image(
    item_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, and WEBP images are supported.",
        )

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")

    item = _owned_item(session, current_user, item_id)
    folder = UPLOAD_ROOT / str(item.business_profile_id)
    folder.mkdir(parents=True, exist_ok=True)

    extension = ALLOWED_TYPES[file.content_type]
    filename = f"item-{item.id}-{uuid4().hex}{extension}"
    file_path = folder / filename
    file_path.write_bytes(content)

    _delete_local_file(item.photo_url)
    item.photo_url = f"/media/menu-items/{item.business_profile_id}/{filename}"
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)

    return {
        "id": item.id,
        "photo_url": item.photo_url,
    }


@router.delete("/{item_id}/image", status_code=204)
def delete_menu_item_image(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    item = _owned_item(session, current_user, item_id)
    _delete_local_file(item.photo_url)
    item.photo_url = None
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
