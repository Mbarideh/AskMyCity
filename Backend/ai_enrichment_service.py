import html
import json
import os
import re
import ssl
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import OpenAI

from models import Place

load_dotenv()

MODEL = os.getenv("OPENAI_ENRICHMENT_MODEL", "gpt-5-mini")
PROMPT_VERSION = "v6-targeted-dietary-official-pages"
HTTP_TIMEOUT = float(os.getenv("AI_HTTP_TIMEOUT_SECONDS", "8"))
HTTP_MAX_BYTES = int(os.getenv("AI_HTTP_MAX_BYTES", "600000"))
PAGE_LIMIT = int(os.getenv("AI_OFFICIAL_PAGE_LIMIT", "2"))
TEXT_LIMIT = int(os.getenv("AI_OFFICIAL_TEXT_LIMIT", "16000"))
MAX_OUTPUT_TOKENS = int(os.getenv("AI_STRUCTURE_MAX_OUTPUT_TOKENS", "1400"))

CONFIDENCE = {"type": "string", "enum": ["low", "medium", "high"]}

SCHEMA = {
    "type": "json_schema",
    "name": "askmycity_enrichment_v5",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "ai_summary": {"type": ["string", "null"]},
            "cuisine_types": {"type": "array", "items": {"type": "string"}},
            "cuisine_confidence": CONFIDENCE,
            "menu_items": {"type": "array", "items": {"type": "string"}},
            "menu_confidence": CONFIDENCE,
            "signature_items": {"type": "array", "items": {"type": "string"}},
            "dish_reputation": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "sentiment": {"type": "string", "enum": ["positive", "mixed", "negative"]},
                        "evidence": {"type": "string"},
                        "confidence": CONFIDENCE,
                    },
                    "required": ["item", "sentiment", "evidence", "confidence"],
                    "additionalProperties": False,
                },
            },
            "price_level": {
                "type": ["string", "null"],
                "enum": ["budget", "moderate", "expensive", "luxury", None],
            },
            "average_main_price_cad": {"type": ["number", "null"], "minimum": 0},
            "price_confidence": CONFIDENCE,
            "value_for_money": {
                "type": ["string", "null"],
                "enum": ["good", "mixed", "poor", None],
            },
            "best_for": {"type": "array", "items": {"type": "string"}},
            "atmosphere": {"type": "array", "items": {"type": "string"}},
            "dietary_options": {"type": "array", "items": {"type": "string"}},
            "service_features": {"type": "array", "items": {"type": "string"}},
            "search_tags": {"type": "array", "items": {"type": "string"}},
            "evidence_summary": {"type": ["string", "null"]},
            "overall_confidence": CONFIDENCE,
            "source_urls": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "ai_summary", "cuisine_types", "cuisine_confidence", "menu_items",
            "menu_confidence", "signature_items", "dish_reputation", "price_level",
            "average_main_price_cad", "price_confidence", "value_for_money",
            "best_for", "atmosphere", "dietary_options", "service_features",
            "search_tags", "evidence_summary", "overall_confidence", "source_urls"
        ],
        "additionalProperties": False,
    },
}

INSTRUCTIONS = """
Create a structured AskMyCity business profile from a business record and
official-page evidence. Return only JSON matching the schema.

Rules:
- Never invent facts.
- Confirm a requested dish only when it appears in supplied official evidence.
- A cuisine association or business name is not proof of a dish.
- Never infer customer reputation without actual review evidence.
- Never guess prices.
- Missing evidence means empty/null fields and low confidence.
- source_urls may contain only URLs explicitly supplied as official sources.
- Keep summaries concise and neutral.
""".strip()


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        elif not self.skip and tag == "a":
            self.href = dict(attrs).get("href")
            self.anchor = []
        elif not self.skip and tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.anchor)))
            self.href = None
            self.anchor = []

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        value = data.strip()
        if value:
            self.parts.append(value)
            if self.href is not None:
                self.anchor.append(value)


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing from Backend/.env")
    return OpenAI(api_key=key, timeout=90.0, max_retries=1)


def _clean_list(value: Any, maximum: int = 30) -> list[str]:
    if not isinstance(value, list):
        return []
    result, seen = [], set()
    for item in value:
        text = str(item).strip()
        key = text.casefold()
        if text and key not in seen:
            result.append(text[:500] if text.startswith("http") else text[:180])
            seen.add(key)
        if len(result) >= maximum:
            break
    return result


def _clean_reputation(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for row in value[:20]:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item", "")).strip()
        evidence = str(row.get("evidence", "")).strip()
        if item and evidence:
            sentiment = row.get("sentiment", "mixed")
            confidence = row.get("confidence", "low")
            result.append({
                "item": item[:120],
                "sentiment": sentiment if sentiment in {"positive", "mixed", "negative"} else "mixed",
                "evidence": evidence[:400],
                "confidence": confidence if confidence in {"low", "medium", "high"} else "low",
            })
    return result


def build_place_payload(place: Place) -> dict[str, Any]:
    return {
        "name": place.name,
        "category": place.category,
        "business_type": place.business_type,
        "subtypes": place.subtypes,
        "description": place.description,
        "address": place.full_address,
        "city": place.city,
        "rating": place.rating,
        "review_count": place.review_count,
        "website": place.website,
        "menu_link": place.menu_link,
        "features": place.features_json,
        "price_range": place.price_range,
        "business_status": place.business_status,
        "google_maps_url": place.google_maps_url,
        "reviews_link": place.reviews_link,
    }


def _debug(response: Any) -> str:
    return (
        f"status={getattr(response, 'status', None)}, "
        f"incomplete={getattr(response, 'incomplete_details', None)}, "
        f"error={getattr(response, 'error', None)}"
    )


def _url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    return url if urlparse(url).netloc else None


def _same_domain(a: str, b: str) -> bool:
    left = urlparse(a).netloc.lower().removeprefix("www.")
    right = urlparse(b).netloc.lower().removeprefix("www.")
    return bool(left and left == right)


def _fetch(url: str) -> tuple[str, list[tuple[str, str]]]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AskMyCityBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-CA,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT, context=ssl.create_default_context()) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                return "", []
            raw = response.read(HTTP_MAX_BYTES)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return "", []

    page = raw.decode("utf-8", errors="replace")
    parser = PageParser()
    try:
        parser.feed(page)
    except Exception:
        return "", []

    text = html.unescape(" ".join(parser.parts))
    text = re.sub(r"\s+", " ", text).strip()[:TEXT_LIMIT]
    links = [(urljoin(url, href), anchor) for href, anchor in parser.links]
    return text, links


def _score_link(url: str, anchor: str, requested_dietary_options: list[str] | None = None) -> int:
    value = f"{url} {anchor}".casefold()
    score = sum(points for word, points in {
        "menu": 10, "order": 8, "food": 5, "dinner": 4,
        "lunch": 4, "takeout": 3, "delivery": 3,
        "about": 4, "faq": 4, "catering": 3
    }.items() if word in value)
    for option in requested_dietary_options or []:
        if str(option).strip().casefold() in value:
            score += 20
    if any(domain in value for domain in ("facebook.com", "instagram.com", "tiktok.com")):
        score -= 20
    return score


def _official_pages(payload: dict[str, Any], requested_dietary_options: list[str] | None = None) -> list[dict[str, str]]:
    urls = []
    for value in (payload.get("menu_link"), payload.get("website")):
        normalized = _url(value)
        if normalized and normalized not in urls:
            urls.append(normalized)

    if not urls:
        return []

    pages: list[dict[str, str]] = []
    fetched: set[str] = set()

    first = urls[0]
    text, links = _fetch(first)
    if text:
        pages.append({"url": first, "text": text})
        fetched.add(first)

    if len(urls) > 1 and len(pages) < PAGE_LIMIT:
        text, _ = _fetch(urls[1])
        if text:
            pages.append({"url": urls[1], "text": text})
            fetched.add(urls[1])

    if len(pages) < PAGE_LIMIT:
        ranked = sorted(
            (
                (link, anchor, _score_link(link, anchor, requested_dietary_options))
                for link, anchor in links
                if _same_domain(first, link) and link not in fetched
            ),
            key=lambda row: row[2],
            reverse=True,
        )
        for link, _, score in ranked:
            if score <= 0:
                break
            text, _ = _fetch(link)
            if text:
                pages.append({"url": link, "text": text})
                break

    return pages[:PAGE_LIMIT]


def _structure(
    payload: dict[str, Any],
    pages: list[dict[str, str]],
    requested_dishes: list[str] | None,
    maximum_price: float | None,
    requested_cuisine: str | None,
    requested_dietary_options: list[str] | None,
) -> dict[str, Any]:
    evidence = "\n\n".join(
        f"OFFICIAL SOURCE\nURL: {page['url']}\nTEXT:\n{page['text']}"
        for page in pages
    ) or "No official-page evidence was retrieved."

    prompt = (
        "USER REQUEST:\n"
        + json.dumps({
            "requested_cuisine": requested_cuisine,
            "requested_dishes": requested_dishes or [],
            "maximum_price_cad": maximum_price,
            "requested_dietary_options": requested_dietary_options or [],
        }, ensure_ascii=False, indent=2)
        + "\n\nBUSINESS RECORD:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nOFFICIAL EVIDENCE:\n"
        + evidence
        + "\n\nFor every requested dietary option, explicitly verify whether the official evidence confirms it. "
          "Do not infer halal, kosher, vegan, or gluten-free status from cuisine, restaurant name, or reviews. "
          "Only include a requested dietary option in dietary_options when the supplied official website/menu text explicitly confirms it. "
          "For a halal request, distinguish a fully halal restaurant from a restaurant that only offers selected halal options. "
          "Only return the dietary option 'halal' when the official evidence says 100% halal, fully halal, certified halal, all meat/food is halal, "
          "the business identifies itself as a halal restaurant, or it explicitly says it serves halal food/meat. "
          "Do not return 'halal' for phrases such as halal options, selected halal items, halal available on request, or a single halal dish. "
          "If full halal status is not confirmed, omit it and state the limitation in the evidence summary."
    )

    response = get_client().responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=prompt,
        text={"format": SCHEMA},
        reasoning={"effort": "minimal"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError("The model returned no JSON. " + _debug(response))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The model returned invalid JSON.") from exc


def enrich_place(
    place: Place,
    use_web_search: bool = False,
    requested_dishes: list[str] | None = None,
    maximum_price: float | None = None,
    requested_cuisine: str | None = None,
    requested_dietary_options: list[str] | None = None,
) -> dict[str, Any]:
    """
    Low-cost design:
    1. Fetch up to two official pages directly.
    2. Make exactly one structured-output AI request.
    3. Never invoke the hosted OpenAI web_search tool.
    """
    payload = build_place_payload(place)
    pages = _official_pages(payload, requested_dietary_options) if use_web_search else []
    data = _structure(
        payload, pages, requested_dishes, maximum_price, requested_cuisine, requested_dietary_options
    )

    allowed = {page["url"].casefold(): page["url"] for page in pages}
    source_urls = [
        allowed[url.casefold()]
        for url in _clean_list(data.get("source_urls"), maximum=10)
        if url.casefold() in allowed
    ]

    return {
        "ai_summary": data.get("ai_summary") or None,
        "cuisine_types": _clean_list(data.get("cuisine_types")),
        "cuisine_confidence": data.get("cuisine_confidence", "low"),
        "menu_items": _clean_list(data.get("menu_items"), maximum=60),
        "menu_confidence": data.get("menu_confidence", "low"),
        "signature_items": _clean_list(data.get("signature_items")),
        "dish_reputation": _clean_reputation(data.get("dish_reputation")),
        "price_level": data.get("price_level"),
        "average_main_price_cad": data.get("average_main_price_cad"),
        "price_confidence": data.get("price_confidence", "low"),
        "value_for_money": data.get("value_for_money"),
        "best_for": _clean_list(data.get("best_for")),
        "atmosphere": _clean_list(data.get("atmosphere")),
        "dietary_options": _clean_list(data.get("dietary_options")),
        "service_features": _clean_list(data.get("service_features")),
        "search_tags": _clean_list(data.get("search_tags"), maximum=40),
        "evidence_summary": data.get("evidence_summary") or None,
        "confidence": data.get("overall_confidence", "low"),
        "source_urls": source_urls,
        "enrichment_mode": "official_pages" if pages else "dataset",
        "model_name": MODEL,
        "prompt_version": PROMPT_VERSION,
    }
