from types import SimpleNamespace

from planner.expertise_engine import assess_expertise


def place(**kwargs):
    defaults = dict(name="Generic Restaurant", category="Restaurant", business_type="Restaurant", subtypes="", description="")
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def profile(**kwargs):
    defaults = dict(
        menu_items_json="[]", signature_items_json="[]", dish_reputation_json="[]",
        ai_summary=None, evidence_summary=None, cuisine_types_json="[]",
        menu_confidence="low", confidence="low",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_dedicated_category_beats_incidental_menu_item():
    specialist = assess_expertise(
        place(name="All Out Burger", category="Hamburger restaurant"), None, "burger"
    )
    incidental = assess_expertise(
        place(name="Riviera", category="Canadian restaurant"),
        profile(menu_items_json='["house burger"]', menu_confidence="high"),
        "burger",
    )
    assert specialist.score > incidental.score
    assert specialist.level == "specialist"


def test_multiple_verified_menu_terms_create_strong_expertise():
    assessment = assess_expertise(
        place(name="Downtown Grill"),
        profile(
            menu_items_json='["classic burger", "cheeseburger", "chicken burger", "veggie burger"]',
            menu_confidence="high",
        ),
        "burger",
    )
    assert assessment.score >= 40
    assert assessment.level in {"relevant", "strong", "specialist"}


def test_broad_cuisine_is_not_specialization():
    assessment = assess_expertise(
        place(name="American Kitchen", category="American restaurant"),
        profile(cuisine_types_json='["American"]', confidence="high"),
        "burger",
    )
    assert assessment.score < 40
    assert assessment.level == "incidental"
