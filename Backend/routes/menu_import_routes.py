from __future__ import annotations

import base64
import html
import json
import os
import re
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from dependencies import get_current_user
from models import BusinessProfile, MenuItem, User, utc_now
from menu_icons import infer_menu_icon

router = APIRouter(prefix="/dashboard/menu-import", tags=["Business Menu Import"])

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 6
MAX_TEXT_CHARS = 50000
MODEL = os.getenv("OPENAI_ENRICHMENT_MODEL", "gpt-5-mini")
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/json",
    "text/html",
}


class MenuDraft(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="Other", max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    price: float | None = Field(default=None, ge=0)
    icon: str | None = None
    is_available: bool = True
    is_featured: bool = False


class MenuExtractionResult(BaseModel):
    items: list[MenuDraft]
    source_summary: str
    warnings: list[str] = Field(default_factory=list)


class MenuBulkImport(BaseModel):
    items: list[MenuDraft] = Field(min_length=1, max_length=500)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


def _require_business_user(user: User) -> None:
    if user.account_type not in {"business_owner", "independent_worker"}:
        raise HTTPException(status_code=403, detail="A business account is required.")


def _profile_for_user(session: Session, user_id: int) -> BusinessProfile | None:
    from sqlmodel import select

    return session.exec(
        select(BusinessProfile).where(BusinessProfile.owner_user_id == user_id)
    ).first()


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is missing from Backend/.env.")
    return OpenAI(api_key=api_key, timeout=90.0, max_retries=1)


def _fetch_url_text(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Enter a valid http or https menu URL.")

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 AskMyCityMenuImporter/1.0",
            "Accept": "text/html,text/plain,application/json",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(900000)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise HTTPException(status_code=422, detail="The menu URL could not be read.") from exc

    text = payload.decode("utf-8", errors="ignore")
    if "html" in content_type.lower() or "<html" in text[:500].lower():
        parser = _VisibleTextParser()
        parser.feed(text)
        text = "\n".join(parser.parts)
    return html.unescape(text)[:MAX_TEXT_CHARS]


def _schema() -> dict:
    return {
        "type": "json_schema",
        "name": "askmycity_menu_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "category": {"type": "string"},
                            "description": {"type": ["string", "null"]},
                            "price": {"type": ["number", "null"]},
                            "is_available": {"type": "boolean"},
                            "is_featured": {"type": "boolean"},
                        },
                        "required": [
                            "name", "category", "description", "price",
                            "is_available", "is_featured",
                        ],
                        "additionalProperties": False,
                    },
                },
                "source_summary": {"type": "string"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["items", "source_summary", "warnings"],
            "additionalProperties": False,
        },
    }


async def _build_inputs(files: list[UploadFile], pasted_text: str, menu_url: str) -> list[dict]:
    content: list[dict] = [{
        "type": "input_text",
        "text": (
            "Extract a restaurant menu from the supplied sources. Return each real menu item once. "
            "Use clear categories, preserve descriptions when available, and use CAD numeric prices "
            "without currency symbols. Never invent an item or price. If a price is unclear, return null. "
            "Ignore navigation, reviews, delivery fees, business hours, and unrelated website text."
        ),
    }]

    if pasted_text.strip():
        content.append({"type": "input_text", "text": "PASTED MENU TEXT:\n" + pasted_text[:MAX_TEXT_CHARS]})

    if menu_url.strip():
        page_text = _fetch_url_text(menu_url.strip())
        content.append({"type": "input_text", "text": f"MENU URL: {menu_url.strip()}\nPAGE TEXT:\n{page_text}"})

    for upload in files[:MAX_FILES]:
        data = await upload.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"{upload.filename} is larger than 10 MB.")
        media_type = (upload.content_type or "application/octet-stream").lower()
        suffix = os.path.splitext(upload.filename or "menu")[1].lower()
        if media_type not in ALLOWED_TYPES and suffix not in {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".csv", ".json", ".html"}:
            raise HTTPException(status_code=415, detail=f"Unsupported menu file: {upload.filename}")

        if media_type.startswith("text/") or suffix in {".txt", ".csv", ".json", ".html"}:
            decoded = data.decode("utf-8", errors="ignore")[:MAX_TEXT_CHARS]
            content.append({"type": "input_text", "text": f"FILE {upload.filename}:\n{decoded}"})
        else:
            encoded = base64.b64encode(data).decode("ascii")
            data_url = f"data:{media_type};base64,{encoded}"
            if media_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                content.append({
                    "type": "input_image",
                    "image_url": data_url,
                    "detail": "high",
                })
            else:
                content.append({
                    "type": "input_file",
                    "filename": upload.filename or "menu-file",
                    "file_data": data_url,
                    "detail": "high",
                })

    if len(content) == 1:
        raise HTTPException(status_code=422, detail="Provide menu photos, a PDF, a URL, or menu text.")
    return content


@router.post("/extract", response_model=MenuExtractionResult)
async def extract_menu(
    files: list[UploadFile] = File(default=[]),
    pasted_text: str = Form(default=""),
    menu_url: str = Form(default=""),
    current_user: User = Depends(get_current_user),
):
    _require_business_user(current_user)
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Upload no more than {MAX_FILES} files at once.")

    inputs = await _build_inputs(files, pasted_text, menu_url)
    try:
        response = _client().responses.create(
            model=MODEL,
            instructions="You are a precise restaurant menu data extraction system.",
            input=[{"role": "user", "content": inputs}],
            reasoning={"effort": "minimal"},
            text={"format": _schema()},
            max_output_tokens=7000,
        )
        data = json.loads(response.output_text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Menu extraction failed: {exc}") from exc

    cleaned: list[MenuDraft] = []
    seen: set[tuple[str, str]] = set()
    for raw in data.get("items", []):
        name = re.sub(r"\s+", " ", str(raw.get("name", ""))).strip()
        category = re.sub(r"\s+", " ", str(raw.get("category") or "Other")).strip()
        if not name:
            continue
        key = (name.lower(), category.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(MenuDraft(
            name=name[:200],
            category=category[:100],
            description=(str(raw.get("description")).strip()[:1000] if raw.get("description") else None),
            price=raw.get("price"),
            is_available=bool(raw.get("is_available", True)),
            is_featured=bool(raw.get("is_featured", False)),
        ))

    return MenuExtractionResult(
        items=cleaned,
        source_summary=str(data.get("source_summary") or f"Extracted {len(cleaned)} menu items."),
        warnings=[str(value) for value in data.get("warnings", [])][:20],
    )


@router.post("/confirm", response_model=list[MenuDraft], status_code=201)
def confirm_menu_import(
    payload: MenuBulkImport,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_business_user(current_user)
    profile = _profile_for_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=409, detail="Create your business profile first.")

    created: list[MenuDraft] = []
    for draft in payload.items:
        data = draft.model_dump()
        data["icon"] = data.get("icon") or infer_menu_icon(data.get("name"), data.get("category"), data.get("description"))
        item = MenuItem(
            business_profile_id=profile.id,
            **data,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(item)
        created.append(draft)
    session.commit()
    return created
