import json
from datetime import datetime, timezone
from sqlmodel import Session, select

from models import BusinessAIProfile, Place


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_list(value: str | None) -> list:
    try:
        loaded = json.loads(value or "[]")
        return loaded if isinstance(loaded, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _merge(existing: str | None, incoming: list, identity_key: str | None = None) -> str:
    merged: list = []
    seen: set[str] = set()
    for item in [*_load_list(existing), *(incoming or [])]:
        if identity_key and isinstance(item, dict):
            identity = str(item.get(identity_key, "")).strip().lower()
        else:
            identity = json.dumps(item, sort_keys=True, ensure_ascii=False).lower()
        if identity and identity not in seen:
            seen.add(identity)
            merged.append(item)
    return json.dumps(merged, ensure_ascii=False)


class KnowledgeRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_place(self, place_id: int) -> Place | None:
        return self.session.get(Place, place_id)

    def get_profile(self, place_id: int) -> BusinessAIProfile | None:
        return self.session.exec(
            select(BusinessAIProfile).where(BusinessAIProfile.place_id == place_id)
        ).first()

    def save_profile(self, place_id: int, data: dict) -> BusinessAIProfile:
        profile = self.get_profile(place_id) or BusinessAIProfile(place_id=place_id)
        profile.ai_summary = data.get("ai_summary") or profile.ai_summary
        profile.cuisine_types_json = _merge(profile.cuisine_types_json, data.get("cuisine_types", []))
        profile.cuisine_confidence = data.get("cuisine_confidence") or profile.cuisine_confidence
        profile.menu_items_json = _merge(profile.menu_items_json, data.get("menu_items", []))
        profile.menu_confidence = data.get("menu_confidence") or profile.menu_confidence
        profile.signature_items_json = _merge(profile.signature_items_json, data.get("signature_items", []))
        profile.dish_reputation_json = _merge(profile.dish_reputation_json, data.get("dish_reputation", []), "item")
        profile.price_level = data.get("price_level") or profile.price_level
        profile.average_main_price_cad = data.get("average_main_price_cad") or profile.average_main_price_cad
        profile.price_confidence = data.get("price_confidence") or profile.price_confidence
        profile.value_for_money = data.get("value_for_money") or profile.value_for_money
        profile.best_for_json = _merge(profile.best_for_json, data.get("best_for", []))
        profile.atmosphere_json = _merge(profile.atmosphere_json, data.get("atmosphere", []))
        profile.dietary_options_json = _merge(profile.dietary_options_json, data.get("dietary_options", []))
        profile.service_features_json = _merge(profile.service_features_json, data.get("service_features", []))
        profile.search_tags_json = _merge(profile.search_tags_json, data.get("search_tags", []))
        profile.evidence_summary = data.get("evidence_summary") or profile.evidence_summary
        profile.confidence = data.get("confidence") or profile.confidence
        profile.source_urls_json = _merge(profile.source_urls_json, data.get("source_urls", []))
        profile.enrichment_mode = data.get("enrichment_mode") or "web"
        profile.model_name = data.get("model_name") or profile.model_name
        profile.prompt_version = data.get("prompt_version") or profile.prompt_version
        profile.updated_at = utc_now()
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile
