import argparse
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from ai_enrichment_service import enrich_place
from database import create_database_tables, engine
from models import BusinessAIProfile, Place


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_json(value: list[str]) -> str:
    return json.dumps(value, ensure_ascii=False)


def save_profile(session: Session, place: Place, data: dict) -> None:
    profile = session.exec(
        select(BusinessAIProfile).where(BusinessAIProfile.place_id == place.id)
    ).first()
    if profile is None:
        profile = BusinessAIProfile(place_id=place.id)

    profile.ai_summary = data["ai_summary"]
    profile.cuisine_types_json = to_json(data["cuisine_types"])
    profile.cuisine_confidence = data["cuisine_confidence"]
    profile.menu_items_json = to_json(data["menu_items"])
    profile.menu_confidence = data["menu_confidence"]
    profile.signature_items_json = to_json(data["signature_items"])
    profile.dish_reputation_json = json.dumps(data["dish_reputation"], ensure_ascii=False)
    profile.price_level = data["price_level"]
    profile.average_main_price_cad = data["average_main_price_cad"]
    profile.price_confidence = data["price_confidence"]
    profile.value_for_money = data["value_for_money"]
    profile.best_for_json = to_json(data["best_for"])
    profile.atmosphere_json = to_json(data["atmosphere"])
    profile.dietary_options_json = to_json(data["dietary_options"])
    profile.service_features_json = to_json(data["service_features"])
    profile.search_tags_json = to_json(data["search_tags"])
    profile.evidence_summary = data["evidence_summary"]
    profile.confidence = data["confidence"]
    profile.source_urls_json = to_json(data["source_urls"])
    profile.enrichment_mode = data["enrichment_mode"]
    profile.model_name = data["model_name"]
    profile.prompt_version = data["prompt_version"]
    profile.updated_at = utc_now()
    session.add(profile)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich AskMyCity businesses using OpenAI.")
    parser.add_argument("--category", default="restaurant")
    parser.add_argument("--city", default="Ottawa")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--start-id", type=int, default=0)
    parser.add_argument("--web", action="store_true", help="Use paid live web search.")
    parser.add_argument("--force", action="store_true", help="Re-enrich existing profiles.")
    args = parser.parse_args()

    create_database_tables()
    with Session(engine) as session:
        statement = select(Place).where(Place.id > args.start_id)
        if args.category:
            statement = statement.where(Place.category.ilike(args.category))
        if args.city:
            statement = statement.where(Place.city.ilike(f"%{args.city}%"))
        statement = statement.order_by(Place.id).limit(max(1, args.limit))
        places = list(session.exec(statement).all())

        completed = 0
        skipped = 0
        failed = 0
        for place in places:
            existing = session.exec(
                select(BusinessAIProfile).where(BusinessAIProfile.place_id == place.id)
            ).first()
            if existing and not args.force:
                print(f"SKIP {place.id}: {place.name} (already enriched)")
                skipped += 1
                continue
            try:
                print(f"ENRICH {place.id}: {place.name}")
                data = enrich_place(place, use_web_search=args.web)
                save_profile(session, place, data)
                session.commit()
                completed += 1
                print(
                    f"  saved: overall={data['confidence']}, "
                    f"cuisine={data['cuisine_confidence']}, "
                    f"menu={data['menu_confidence']}, "
                    f"price={data['price_confidence']}, "
                    f"sources={len(data['source_urls'])}"
                )
            except Exception as error:
                session.rollback()
                failed += 1
                print(f"  FAILED: {error}")

    print("\nFinished")
    print(f"Completed: {completed}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")


if __name__ == "__main__":
    main()
