import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook
from sqlmodel import Session, select

from database import create_database_tables, engine
from models import BusinessAIProfile, ImportBatch, Place


ROOT = Path(__file__).resolve().parent
DEFAULT_RESTAURANT_FILE = (
    ROOT / "Outscraper-20260727204522s01f2_restaurants.xlsx"
)
DEFAULT_PLUMBER_FILE = ROOT / "plumbers.csv"

# The enriched workbook is the canonical restaurant dataset.  Its first sheet
# still contains the original Outscraper rows, while the extra columns/sheets
# contain offline enrichment.  Importing it does not call any paid API.
ENRICHED_PROFILE_FIELDS = {
    "ai_summary", "ai_search_tags", "halal_status", "halal_confidence",
    "halal_source", "halal_source_url", "halal_evidence", "halal_last_verified",
    "price_level", "average_meal_price", "family_friendly", "kids_menu",
    "high_chair", "wheelchair_accessible", "parking_available", "patio",
    "takeout", "delivery", "reservations", "wifi", "vegan", "vegetarian",
    "gluten_free", "casual", "cozy", "modern", "luxury", "fine_dining",
    "quiet", "trendy", "good_for_groups", "romantic",
}



def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text if text else None


def convert_float(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def convert_integer(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return int(float(text.replace(",", "")))
    except (TypeError, ValueError):
        return None


def convert_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value)
    return bool(text and text.lower() in {"true", "1", "yes", "y"})


def json_text(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except (TypeError, ValueError, json.JSONDecodeError):
        return text


def make_business_id(row: dict[str, Any]) -> str:
    for key in ("business_id", "place_id", "google_id", "cid"):
        value = clean_text(row.get(key))
        if value:
            return value

    raw = "|".join(
        filter(
            None,
            [
                clean_text(row.get("name")),
                clean_text(row.get("address") or row.get("full_address")),
                clean_text(row.get("phone") or row.get("phone_number")),
            ],
        )
    )
    return "generated-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def read_csv_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def read_excel_rows(path: Path) -> Iterable[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    iterator = worksheet.iter_rows(values_only=True)
    headers = [clean_text(value) or "" for value in next(iterator)]
    for values in iterator:
        yield dict(zip(headers, values, strict=False))
    workbook.close()


def read_rows(path: Path) -> Iterable[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        yield from read_csv_rows(path)
    elif suffix in {".xlsx", ".xlsm"}:
        yield from read_excel_rows(path)
    else:
        raise ValueError("Supported file types are CSV and XLSX.")


def normalized_category(row: dict[str, Any], fallback: str) -> str:
    """
    Return the canonical AskMyCity category selected for the import.

    Outscraper's ``category`` column is not stable enough to use as the
    primary search category. A restaurant search can return values such as
    ``restaurants``, ``bars``, ``cafes`` or a specific cuisine. Those useful
    details are already preserved in ``business_type`` and ``subtypes``.

    The importer therefore uses the category supplied on the command line
    as the canonical category, so every business from the Ottawa restaurant
    file can be found with the singular filter ``restaurant``.
    """

    canonical = clean_text(fallback) or "business"
    canonical = canonical.lower().strip()

    singular_aliases = {
        "restaurants": "restaurant",
        "plumbers": "plumber",
        "dentists": "dentist",
        "electricians": "electrician",
        "lawyers": "lawyer",
        "mechanics": "mechanic",
    }

    return singular_aliases.get(canonical, canonical)


def map_row(row: dict[str, Any], fallback_category: str) -> dict[str, Any]:
    return {
        "business_id": make_business_id(row),
        "place_id": clean_text(row.get("place_id")),
        "google_id": clean_text(row.get("google_id")),
        "cid": clean_text(row.get("cid")),
        "name": clean_text(row.get("name")),
        "category": normalized_category(row, fallback_category),
        "business_type": clean_text(row.get("type")),
        "subtypes": clean_text(row.get("subtypes")),
        "full_address": clean_text(row.get("address") or row.get("full_address")),
        "street": clean_text(row.get("street")),
        "city": clean_text(row.get("city")),
        "county": clean_text(row.get("county")),
        "state": clean_text(row.get("state")),
        "postal_code": clean_text(row.get("postal_code")),
        "country": clean_text(row.get("country")),
        "latitude": convert_float(row.get("latitude")),
        "longitude": convert_float(row.get("longitude")),
        "time_zone": clean_text(row.get("time_zone")),
        "rating": convert_float(row.get("rating")),
        "review_count": convert_integer(row.get("reviews") or row.get("review_count")),
        "reviews_1_star": convert_integer(row.get("reviews_per_score_1")),
        "reviews_2_star": convert_integer(row.get("reviews_per_score_2")),
        "reviews_3_star": convert_integer(row.get("reviews_per_score_3")),
        "reviews_4_star": convert_integer(row.get("reviews_per_score_4")),
        "reviews_5_star": convert_integer(row.get("reviews_per_score_5")),
        "reviews_link": clean_text(row.get("reviews_link")),
        "phone_number": clean_text(row.get("phone") or row.get("phone_number")),
        "website": clean_text(row.get("website")),
        "google_maps_url": clean_text(row.get("location_link") or row.get("place_link")),
        "photo_url": clean_text(row.get("photo")),
        "logo_url": clean_text(row.get("logo")),
        "street_view_url": clean_text(row.get("street_view")),
        "business_status": clean_text(row.get("business_status")),
        "price_range": clean_text(row.get("range")),
        "working_hours_json": json_text(row.get("working_hours")),
        "other_hours_json": json_text(row.get("other_hours")),
        "features_json": json_text(row.get("about")),
        "reservation_links": clean_text(row.get("reservation_links")),
        "menu_link": clean_text(row.get("menu_link")),
        "order_links": clean_text(row.get("order_links")),
        "verified": convert_boolean(row.get("verified")),
        "description": clean_text(row.get("description") or row.get("website_description")),
        "source": "outscraper_file",
        "source_query": clean_text(row.get("query")),
        "updated_at": utc_now(),
    }


def _truthy_enriched(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = (clean_text(value) or "").lower()
    return text in {"true", "1", "yes", "y", "verified", "available"}


def _json_list(values: Iterable[str]) -> str | None:
    cleaned = list(dict.fromkeys(v.strip().lower() for v in values if v and v.strip()))
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def update_enriched_profile(session: Session, place: Place, row: dict[str, Any]) -> bool:
    """Persist offline workbook enrichment in BusinessAIProfile.

    Important: `halal_options` is intentionally NOT promoted to verified halal.
    Only a full/verified halal status becomes the strict `halal` dietary option.
    This keeps the existing search rule from presenting partial options as a
    fully verified halal restaurant.
    """
    if place.id is None:
        session.flush()

    profile = session.exec(
        select(BusinessAIProfile).where(BusinessAIProfile.place_id == place.id)
    ).first()
    if profile is None:
        profile = BusinessAIProfile(place_id=place.id)

    changed = False
    summary = clean_text(row.get("ai_summary"))
    if summary and profile.ai_summary != summary:
        profile.ai_summary = summary
        changed = True

    tags = [x.strip() for x in (clean_text(row.get("ai_search_tags")) or "").split(",") if x.strip()]
    halal_status = (clean_text(row.get("halal_status")) or "").lower().replace(" ", "_")
    halal_confidence = convert_float(row.get("halal_confidence")) or 0.0
    full_halal = halal_status in {"halal", "verified_halal", "fully_halal", "certified_halal"}
    halal_options = halal_status in {"halal_options", "partial_halal", "some_halal_options"}

    dietary = []
    for key, label in (("vegan", "vegan"), ("vegetarian", "vegetarian"), ("gluten_free", "gluten free")):
        if _truthy_enriched(row.get(key)):
            dietary.append(label)
    if full_halal and halal_confidence >= 0.70:
        dietary.append("halal")
    dietary_json = _json_list(dietary)
    if dietary_json and profile.dietary_options_json != dietary_json:
        profile.dietary_options_json = dietary_json
        changed = True

    service = []
    for key, label in (
        ("family_friendly", "family friendly"), ("kids_menu", "kids menu"),
        ("high_chair", "high chair"), ("wheelchair_accessible", "wheelchair accessible"),
        ("parking_available", "parking"), ("patio", "patio"), ("takeout", "takeout"),
        ("delivery", "delivery"), ("reservations", "reservations"), ("wifi", "wifi"),
        ("good_for_groups", "good for groups"),
    ):
        if _truthy_enriched(row.get(key)):
            service.append(label)
    if halal_options:
        service.append("halal options")
    service_json = _json_list(service)
    if service_json and profile.service_features_json != service_json:
        profile.service_features_json = service_json
        changed = True

    atmosphere = []
    for key in ("casual", "cozy", "modern", "luxury", "fine_dining", "quiet", "trendy", "romantic"):
        if _truthy_enriched(row.get(key)):
            atmosphere.append(key.replace("_", " "))
    atmosphere_json = _json_list(atmosphere)
    if atmosphere_json and profile.atmosphere_json != atmosphere_json:
        profile.atmosphere_json = atmosphere_json
        changed = True

    if tags:
        tags_json = _json_list(tags)
        if tags_json and profile.search_tags_json != tags_json:
            profile.search_tags_json = tags_json
            changed = True

    price_level = clean_text(row.get("price_level"))
    if price_level and profile.price_level != price_level:
        profile.price_level = price_level
        changed = True
    avg_price = convert_float(row.get("average_meal_price"))
    if avg_price is not None and profile.average_main_price_cad != avg_price:
        profile.average_main_price_cad = avg_price
        changed = True

    evidence = clean_text(row.get("halal_evidence"))
    source_url = clean_text(row.get("halal_source_url"))
    if full_halal and evidence:
        profile.evidence_summary = evidence
        changed = True
    if source_url:
        urls = [source_url]
        if place.website:
            urls.append(place.website)
        urls_json = _json_list(urls)
        if urls_json and profile.source_urls_json != urls_json:
            profile.source_urls_json = urls_json
            changed = True

    # Offline verified data is authoritative enough for database-first search.
    if full_halal and halal_confidence >= 0.70:
        profile.confidence = "high"
    elif halal_options or dietary or service or tags:
        profile.confidence = "medium" if profile.confidence != "high" else "high"
    profile.enrichment_mode = "dataset"
    profile.model_name = "offline-enriched-workbook"
    profile.prompt_version = "offline-enrichment-v1"
    if changed:
        profile.updated_at = utc_now()
        session.add(profile)
    return changed


def find_existing(session: Session, data: dict[str, Any]) -> Place | None:
    for column, value in (
        (Place.place_id, data.get("place_id")),
        (Place.google_id, data.get("google_id")),
        (Place.cid, data.get("cid")),
        (Place.business_id, data.get("business_id")),
    ):
        if value:
            match = session.exec(select(Place).where(column == value)).first()
            if match:
                return match
    return None


def update_place(place: Place, data: dict[str, Any]) -> bool:
    changed = False
    for field_name, new_value in data.items():
        if field_name in {"business_id", "imported_at"}:
            continue
        if new_value is not None and getattr(place, field_name) != new_value:
            setattr(place, field_name, new_value)
            changed = True
    if changed:
        place.updated_at = utc_now()
    return changed


def import_file(path: Path, category: str) -> dict[str, int]:
    create_database_tables()
    counters = {"imported": 0, "updated": 0, "skipped": 0, "failed": 0}
    detected_cities: set[str] = set()

    with Session(engine) as session:
        for row_number, row in enumerate(read_rows(path), start=2):
            try:
                data = map_row(row, category)
                if not data["name"]:
                    counters["skipped"] += 1
                    print(f"Skipped row {row_number}: missing business name")
                    continue

                if data.get("city"):
                    detected_cities.add(data["city"])

                existing = find_existing(session, data)
                profile_changed = False
                if existing:
                    # A restaurant import must never overwrite plumbers or a
                    # manually-created Business Studio record with another category.
                    if category.lower() == "restaurant" and (existing.category or "").lower() not in {"restaurant", "restaurants"}:
                        counters["skipped"] += 1
                        print(f"Skipped row {row_number}: matched non-restaurant record {existing.business_id}")
                        continue
                    place_changed = update_place(existing, data)
                    if place_changed:
                        session.add(existing)
                    profile_changed = update_enriched_profile(session, existing, row)
                    if place_changed or profile_changed:
                        counters["updated"] += 1
                    else:
                        counters["skipped"] += 1
                else:
                    new_place = Place(**data, imported_at=utc_now())
                    session.add(new_place)
                    session.flush()
                    update_enriched_profile(session, new_place, row)
                    counters["imported"] += 1

                if sum(counters.values()) % 100 == 0:
                    session.commit()
                    print(f"Processed {sum(counters.values())} rows...")
            except Exception as error:
                session.rollback()
                counters["failed"] += 1
                print(f"Failed row {row_number}: {error}")

        session.commit()
        batch = ImportBatch(
            source="outscraper_file",
            source_file=path.name,
            city=", ".join(sorted(detected_cities)) or None,
            category=category.lower(),
            imported_count=counters["imported"],
            updated_count=counters["updated"],
            skipped_count=counters["skipped"],
            failed_count=counters["failed"],
            is_paid_api_request=False,
        )
        session.add(batch)
        session.commit()

    print("\nImport completed")
    for key, value in counters.items():
        print(f"{key.title()}: {value}")
    return counters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Outscraper CSV/XLSX data into AskMyCity."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_RESTAURANT_FILE,
        help="CSV or XLSX file. Defaults to the paid Ottawa restaurant file.",
    )
    parser.add_argument(
        "--category",
        default="restaurant",
        help="Fallback category when the source row has no category.",
    )
    parser.add_argument(
        "--plumbers",
        action="store_true",
        help="Use the existing plumbers.csv file and plumber category.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    selected_file = DEFAULT_PLUMBER_FILE if arguments.plumbers else arguments.file
    selected_category = "plumber" if arguments.plumbers else arguments.category
    if not selected_file.exists():
        raise FileNotFoundError(f"File not found: {selected_file}")
    import_file(selected_file, selected_category)
