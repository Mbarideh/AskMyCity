from __future__ import annotations

RULES: list[tuple[tuple[str, ...], str]] = [
    (("cappuccino", "espresso", "latte", "coffee", "americano", "macchiato", "mocha"), "☕"),
    (("tea", "chai", "matcha"), "🍵"),
    (("soda", "cola", "coke", "pepsi", "soft drink", "fountain drink"), "🥤"),
    (("juice", "lemonade", "smoothie", "shake"), "🧃"),
    (("water", "sparkling water"), "💧"),
    (("beer", "lager", "ale", "ipa"), "🍺"),
    (("wine", "merlot", "cabernet", "pinot", "chardonnay"), "🍷"),
    (("cocktail", "martini", "margarita", "mojito"), "🍸"),
    (("steak", "beef", "ribeye", "sirloin", "filet mignon"), "🥩"),
    (("salmon", "fish", "cod", "tuna", "trout", "tilapia"), "🐟"),
    (("chicken", "wings", "drumstick"), "🍗"),
    (("burger", "cheeseburger", "hamburger"), "🍔"),
    (("pizza", "pepperoni", "margherita"), "🍕"),
    (("spaghetti", "pasta", "lasagna", "fettuccine", "linguine", "ravioli", "penne", "alfredo", "marinara"), "🍝"),
    (("salad", "caesar", "greens"), "🥗"),
    (("soup", "chowder", "bisque"), "🍲"),
    (("sandwich", "panini", "sub", "wrap"), "🥪"),
    (("taco", "tacos"), "🌮"),
    (("burrito", "quesadilla"), "🌯"),
    (("sushi", "sashimi", "nigiri", "maki"), "🍣"),
    (("ramen", "noodle", "pho"), "🍜"),
    (("rice", "risotto"), "🍚"),
    (("fries", "french fries", "poutine"), "🍟"),
    (("breakfast", "egg", "omelette", "omelet"), "🍳"),
    (("pancake", "waffle", "crepe"), "🥞"),
    (("bread", "baguette", "toast"), "🥖"),
    (("cheesecake", "tiramisu", "cake", "dessert", "pie"), "🍰"),
    (("ice cream", "gelato", "sorbet"), "🍨"),
    (("cookie", "cookies"), "🍪"),
    (("donut", "doughnut"), "🍩"),
    (("fruit", "strawberry", "berries"), "🍓"),
    (("vegetarian", "vegan", "broccoli", "vegetable"), "🥦"),
]

CATEGORY_ICONS = {
    "appetizer": "🥟", "appetizers": "🥟", "entree": "🍽️", "entrees": "🍽️", "entrées": "🍽️",
    "main": "🍽️", "mains": "🍽️", "food": "🍽️", "pasta": "🍝", "pizza": "🍕",
    "salad": "🥗", "salads": "🥗", "soup": "🍲", "soups": "🍲", "dessert": "🍰",
    "desserts": "🍰", "beverage": "🥤", "beverages": "🥤", "drink": "🥤", "drinks": "🥤",
    "coffee": "☕", "breakfast": "🍳", "brunch": "🥞", "lunch": "🥪", "dinner": "🍽️",
    "kids": "🧒", "kids menu": "🧒", "side": "🍟", "sides": "🍟", "seafood": "🐟",
    "sushi": "🍣", "other": "🍴",
}


def infer_menu_icon(name: str | None, category: str | None = None, description: str | None = None) -> str:
    haystack = " ".join(str(value or "").lower().strip() for value in (name, description, category))
    for keywords, icon in RULES:
        if any(keyword in haystack for keyword in keywords):
            return icon
    return CATEGORY_ICONS.get(str(category or "").lower().strip(), "🍴")
