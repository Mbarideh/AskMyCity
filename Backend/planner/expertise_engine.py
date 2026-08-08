from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from planner.knowledge_engine import get_concept, matched_concept_terms


@dataclass(frozen=True)
class ExpertiseAssessment:
    """Deterministic specialization assessment for one requested concept.

    The score measures how strongly a business specializes in the requested
    concept. It is deliberately separate from quality, distance, and popularity.
    """

    concept: str
    score: int
    level: str
    reasons: tuple[str, ...]
    dedicated_specialist: bool


def _text(*values: Any) -> str:
    return " ".join(str(value) for value in values if value).lower()


def _json_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return str(value).lower()
    return json.dumps(parsed, ensure_ascii=False).lower()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text) is not None


def assess_expertise(place: Any, profile: Any | None, requested_concept: str) -> ExpertiseAssessment:
    """Assess how specialized ``place`` is in ``requested_concept``.

    Evidence weights:
    - exact dedicated category: strongest signal;
    - concept in business name: very strong signal;
    - multiple official menu/signature items: strong signal;
    - positive dish reputation and official summary: supporting signals;
    - broad cuisine relationship: discovery signal only, never specialization.
    """

    concept = get_concept(requested_concept)
    normalized = concept.name if concept else requested_concept.strip().lower()

    name_text = _text(getattr(place, "name", None))
    category_text = _text(
        getattr(place, "category", None),
        getattr(place, "business_type", None),
        getattr(place, "subtypes", None),
    )
    description_text = _text(getattr(place, "description", None))

    menu_text = ""
    signature_text = ""
    reputation_text = ""
    summary_text = ""
    cuisine_text = ""
    menu_confidence = "low"
    profile_confidence = "low"
    if profile is not None:
        menu_text = _json_text(getattr(profile, "menu_items_json", None))
        signature_text = _json_text(getattr(profile, "signature_items_json", None))
        reputation_text = _json_text(getattr(profile, "dish_reputation_json", None))
        summary_text = _text(getattr(profile, "ai_summary", None), getattr(profile, "evidence_summary", None))
        cuisine_text = _json_text(getattr(profile, "cuisine_types_json", None))
        menu_confidence = str(getattr(profile, "menu_confidence", "low") or "low").lower()
        profile_confidence = str(getattr(profile, "confidence", "low") or "low").lower()

    score = 0
    reasons: list[str] = []
    dedicated = False

    categories = concept.categories if concept else ()
    exact_category_matches = [category for category in categories if _contains_phrase(category_text, category)]
    if exact_category_matches:
        score += 48
        dedicated = True
        reasons.append(f"Dedicated {normalized} business category")

    # A concept in the business name is a very strong specialization signal.
    name_matches = matched_concept_terms(name_text, normalized)
    if name_matches:
        score += 28
        dedicated = True
        reasons.append(f"{normalized.title()} is part of the business identity")

    menu_matches = set(matched_concept_terms(menu_text, normalized))
    signature_matches = set(matched_concept_terms(signature_text, normalized))
    official_matches = menu_matches | signature_matches
    if official_matches and menu_confidence in {"medium", "high"}:
        # Multiple distinct matching menu terms suggest depth, not one incidental item.
        score += min(45, 20 + 7 * len(official_matches))
        if len(official_matches) >= 3:
            dedicated = True
            reasons.append(f"Broad verified {normalized} menu")
        else:
            reasons.append(f"Verified {normalized} menu evidence")

    if matched_concept_terms(reputation_text, normalized) and profile_confidence in {"medium", "high"}:
        score += 10
        reasons.append(f"Customer evidence supports {normalized}")

    if matched_concept_terms(summary_text, normalized) and profile_confidence in {"medium", "high"}:
        score += 8
        reasons.append(f"Verified profile emphasizes {normalized}")

    if matched_concept_terms(description_text, normalized):
        score += 5

    # Cuisine is intentionally weak: an American restaurant may serve a burger,
    # but it is not automatically a burger specialist.
    if concept and concept.cuisines and any(_contains_phrase(cuisine_text + " " + category_text, cuisine) for cuisine in concept.cuisines):
        score += 3

    score = max(0, min(100, score))
    if score >= 75:
        level = "specialist"
    elif score >= 60:
        level = "strong"
    elif score >= 40:
        level = "relevant"
    else:
        level = "incidental"

    if not reasons:
        reasons.append(f"Limited {normalized} specialization evidence")

    return ExpertiseAssessment(
        concept=normalized,
        score=score,
        level=level,
        reasons=tuple(reasons[:3]),
        dedicated_specialist=dedicated and score >= 60,
    )


def assess_requested_expertise(place: Any, profile: Any | None, requested_concepts: list[str]) -> ExpertiseAssessment | None:
    """Return the weakest assessment when several concepts are mandatory."""
    if not requested_concepts:
        return None
    assessments = [assess_expertise(place, profile, concept) for concept in requested_concepts]
    return min(assessments, key=lambda item: item.score)
