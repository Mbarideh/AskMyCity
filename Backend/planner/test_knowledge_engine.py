from planner.knowledge_engine import (
    category_proves_concept,
    normalize_concept,
    text_matches_concept,
)


def test_burger_alias_normalization() -> None:
    assert normalize_concept("burgers") == "burger"
    assert normalize_concept("cheeseburger") == "burger"


def test_dedicated_category_is_evidence() -> None:
    assert category_proves_concept("Hamburger restaurant", "burger")
    assert category_proves_concept("Pizza restaurant", "pizza")


def test_menu_family_matching() -> None:
    assert text_matches_concept("Classic cheeseburger", "burger")
    assert text_matches_concept("Tonkotsu ramen", "ramen")


def test_specific_unknown_dish_stays_strict() -> None:
    assert not category_proves_concept("Italian restaurant", "gnocchi")
