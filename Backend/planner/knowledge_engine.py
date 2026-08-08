from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Concept:
    name: str
    aliases: tuple[str, ...]
    categories: tuple[str, ...] = ()
    cuisines: tuple[str, ...] = ()
    menu_terms: tuple[str, ...] = ()
    category_is_evidence: bool = False


CONCEPTS: dict[str, Concept] = {
    "burger": Concept(
        name="burger",
        aliases=("burger", "burgers", "hamburger", "hamburgers", "cheeseburger", "cheeseburgers", "smash burger", "smashburger"),
        categories=("hamburger restaurant", "burger restaurant"),
        cuisines=(),
        menu_terms=("burger", "hamburger", "cheeseburger", "smash burger", "beef burger", "chicken burger", "veggie burger", "double burger"),
        category_is_evidence=True,
    ),
    "pizza": Concept(
        name="pizza",
        aliases=("pizza", "pizzas", "pizzeria", "pizza place"),
        categories=("pizza restaurant", "pizzeria"),
        cuisines=("italian",),
        menu_terms=("pizza", "margherita", "pepperoni pizza", "neapolitan pizza"),
        category_is_evidence=True,
    ),
    "sushi": Concept(
        name="sushi",
        aliases=("sushi", "maki", "nigiri", "sashimi", "sushi rolls"),
        categories=("sushi restaurant",),
        cuisines=("japanese",),
        menu_terms=("sushi", "maki", "nigiri", "sashimi", "temaki"),
        category_is_evidence=True,
    ),
    "coffee": Concept(
        name="coffee",
        aliases=("coffee", "cafe", "café", "coffee shop"),
        categories=("coffee shop", "cafe", "café"),
        menu_terms=("coffee", "espresso", "latte", "americano", "cappuccino", "cold brew"),
        category_is_evidence=True,
    ),
    "shawarma": Concept(
        name="shawarma",
        aliases=("shawarma", "shawarma wrap", "shawarma plate"),
        categories=("shawarma restaurant",),
        cuisines=("middle eastern", "lebanese", "syrian"),
        menu_terms=("shawarma", "chicken shawarma", "beef shawarma", "mixed shawarma"),
        category_is_evidence=True,
    ),
    "ramen": Concept(
        name="ramen",
        aliases=("ramen", "ramen noodles"),
        categories=("ramen restaurant",),
        cuisines=("japanese",),
        menu_terms=("ramen", "tonkotsu", "shoyu ramen", "miso ramen"),
        category_is_evidence=True,
    ),
}


_ALIAS_TO_CONCEPT: dict[str, str] = {}
for concept_name, concept in CONCEPTS.items():
    for term in (concept.name, *concept.aliases, *concept.menu_terms):
        _ALIAS_TO_CONCEPT[term.lower()] = concept_name


def normalize_concept(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    return _ALIAS_TO_CONCEPT.get(cleaned, cleaned)


def get_concept(value: str | None) -> Concept | None:
    normalized = normalize_concept(value)
    return CONCEPTS.get(normalized or "")


def concept_terms(value: str | None) -> set[str]:
    concept = get_concept(value)
    if concept is None:
        return {value.strip().lower()} if value and value.strip() else set()
    return {
        concept.name,
        *concept.aliases,
        *concept.categories,
        *concept.menu_terms,
    }


def concept_cuisines(value: str | None) -> tuple[str, ...]:
    concept = get_concept(value)
    return concept.cuisines if concept else ()


def category_proves_concept(category_text: str | None, value: str | None) -> bool:
    concept = get_concept(value)
    if concept is None or not concept.category_is_evidence or not category_text:
        return False
    normalized = category_text.lower()
    return any(_contains_phrase(normalized, category) for category in concept.categories)


def text_matches_concept(text: str, value: str | None) -> bool:
    if not text or not value:
        return False
    normalized = text.lower()
    return any(_contains_phrase(normalized, term) for term in concept_terms(value))


def matched_concept_terms(text: str, value: str | None) -> list[str]:
    if not text or not value:
        return []
    normalized = text.lower()
    return sorted(term for term in concept_terms(value) if _contains_phrase(normalized, term))


def expand_requested_dishes(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_concept(value) or ""
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text) is not None
