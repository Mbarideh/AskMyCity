from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_user
from models import BusinessMedia, BusinessProfile, Place, User, utc_now

router = APIRouter(prefix="/dashboard/media", tags=["Business media"])
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "businesses"
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_FILE_SIZE = 8 * 1024 * 1024

def _profile(session: Session, user: User) -> BusinessProfile:
    profile = session.exec(select(BusinessProfile).where(BusinessProfile.owner_user_id == user.id)).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your business profile before uploading photos.")
    return profile

def _public(item: BusinessMedia) -> dict:
    return {"id": item.id, "media_type": item.media_type, "file_url": item.file_url, "original_name": item.original_name, "sort_order": item.sort_order, "created_at": item.created_at}

@router.get("")
def list_media(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    profile = _profile(session, current_user)
    items = session.exec(select(BusinessMedia).where(BusinessMedia.business_profile_id == profile.id).order_by(BusinessMedia.media_type, BusinessMedia.sort_order, BusinessMedia.created_at)).all()
    return [_public(item) for item in items]

@router.post("/{media_type}", status_code=201)
async def upload_media(media_type: str, file: UploadFile = File(...), current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if media_type not in {"logo", "cover", "gallery"}:
        raise HTTPException(status_code=400, detail="Media type must be logo, cover, or gallery.")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, and WEBP images are supported.")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    profile = _profile(session, current_user)
    if media_type == "gallery":
        count = len(session.exec(select(BusinessMedia).where(BusinessMedia.business_profile_id == profile.id, BusinessMedia.media_type == "gallery")).all())
        if count >= 12:
            raise HTTPException(status_code=400, detail="A business can have up to 12 gallery photos.")
    folder = UPLOAD_ROOT / str(profile.id)
    folder.mkdir(parents=True, exist_ok=True)
    extension = ALLOWED_TYPES[file.content_type]
    filename = f"{media_type}-{uuid4().hex}{extension}"
    (folder / filename).write_bytes(content)
    url = f"/media/businesses/{profile.id}/{filename}"
    if media_type in {"logo", "cover"}:
        old_items = session.exec(select(BusinessMedia).where(BusinessMedia.business_profile_id == profile.id, BusinessMedia.media_type == media_type)).all()
        for old in old_items:
            old_path = Path(__file__).resolve().parent.parent / old.file_url.lstrip("/media/")
            if old_path.exists(): old_path.unlink(missing_ok=True)
            session.delete(old)
    sort_order = len(session.exec(select(BusinessMedia).where(BusinessMedia.business_profile_id == profile.id, BusinessMedia.media_type == media_type)).all())
    item = BusinessMedia(business_profile_id=profile.id, media_type=media_type, file_url=url, original_name=file.filename, sort_order=sort_order)
    session.add(item)
    if media_type == "logo": profile.logo_url = url
    elif media_type == "cover": profile.cover_photo_url = url
    profile.updated_at = utc_now(); session.add(profile)
    if profile.place_id:
        place = session.get(Place, profile.place_id)
        if place:
            if media_type == "logo": place.logo_url = url
            elif media_type == "cover": place.photo_url = url
            place.updated_at = utc_now(); session.add(place)
    session.commit(); session.refresh(item)
    return _public(item)

@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    profile = _profile(session, current_user)
    item = session.get(BusinessMedia, media_id)
    if not item or item.business_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Photo not found.")
    local_path = Path(__file__).resolve().parent.parent / item.file_url.lstrip("/media/")
    if local_path.exists(): local_path.unlink(missing_ok=True)
    if item.media_type == "logo": profile.logo_url = None
    if item.media_type == "cover": profile.cover_photo_url = None
    session.delete(item); session.add(profile)
    if profile.place_id:
        place = session.get(Place, profile.place_id)
        if place:
            if item.media_type == "logo": place.logo_url = None
            if item.media_type == "cover": place.photo_url = profile.logo_url
            session.add(place)
    session.commit()
