const RULES = [
  [["cappuccino", "espresso", "latte", "coffee", "americano", "macchiato", "mocha"], "☕"],
  [["tea", "chai", "matcha"], "🍵"],
  [["soda", "cola", "coke", "pepsi", "soft drink", "fountain drink"], "🥤"],
  [["juice", "lemonade", "smoothie", "shake"], "🧃"],
  [["water", "sparkling water"], "💧"],
  [["beer", "lager", "ale", "ipa"], "🍺"],
  [["wine", "merlot", "cabernet", "pinot", "chardonnay"], "🍷"],
  [["cocktail", "martini", "margarita", "mojito"], "🍸"],
  [["steak", "beef", "ribeye", "sirloin", "filet mignon"], "🥩"],
  [["salmon", "fish", "cod", "tuna", "trout", "tilapia"], "🐟"],
  [["chicken", "wings", "drumstick"], "🍗"],
  [["burger", "cheeseburger", "hamburger"], "🍔"],
  [["pizza", "pepperoni", "margherita"], "🍕"],
  [["spaghetti", "pasta", "lasagna", "fettuccine", "linguine", "ravioli", "penne", "alfredo", "marinara"], "🍝"],
  [["salad", "caesar", "greens"], "🥗"],
  [["soup", "chowder", "bisque"], "🍲"],
  [["sandwich", "panini", "sub", "wrap"], "🥪"],
  [["taco", "tacos"], "🌮"],
  [["burrito", "quesadilla"], "🌯"],
  [["sushi", "sashimi", "nigiri", "maki"], "🍣"],
  [["ramen", "noodle", "pho"], "🍜"],
  [["rice", "risotto"], "🍚"],
  [["fries", "french fries", "poutine"], "🍟"],
  [["breakfast", "egg", "omelette", "omelet"], "🍳"],
  [["pancake", "waffle", "crepe"], "🥞"],
  [["bread", "baguette", "toast"], "🥖"],
  [["cheesecake", "tiramisu", "cake", "dessert", "pie"], "🍰"],
  [["ice cream", "gelato", "sorbet"], "🍨"],
  [["cookie", "cookies"], "🍪"],
  [["donut", "doughnut"], "🍩"],
  [["fruit", "strawberry", "berries"], "🍓"],
  [["vegetarian", "vegan", "broccoli", "vegetable"], "🥦"],
];

const CATEGORY_ICONS = {
  appetizer: "🥟",
  appetizers: "🥟",
  entree: "🍽️",
  entrees: "🍽️",
  "entrées": "🍽️",
  main: "🍽️",
  mains: "🍽️",
  food: "🍽️",
  pasta: "🍝",
  pizza: "🍕",
  salad: "🥗",
  salads: "🥗",
  soup: "🍲",
  soups: "🍲",
  dessert: "🍰",
  desserts: "🍰",
  beverage: "🥤",
  beverages: "🥤",
  drink: "🥤",
  drinks: "🥤",
  coffee: "☕",
  breakfast: "🍳",
  brunch: "🥞",
  lunch: "🥪",
  dinner: "🍽️",
  kids: "🧒",
  "kids menu": "🧒",
  sides: "🍟",
  side: "🍟",
  seafood: "🐟",
  sushi: "🍣",
  other: "🍴",
};

function clean(value) {
  return String(value || "").trim().toLowerCase();
}

export function getMenuCategoryIcon(category) {
  return CATEGORY_ICONS[clean(category)] || "🍴";
}

export function inferMenuItemIcon(item = {}) {
  const explicit = String(item.icon || "").trim();
  if (explicit) return explicit;

  const haystack = `${clean(item.name)} ${clean(item.description)} ${clean(item.category)}`;
  for (const [keywords, icon] of RULES) {
    if (keywords.some((keyword) => haystack.includes(keyword))) return icon;
  }
  return getMenuCategoryIcon(item.category);
}

export const MENU_ICON_OPTIONS = [
  "🍽️", "🍴", "🥩", "🐟", "🍗", "🍔", "🍕", "🍝", "🥗", "🍲",
  "🥪", "🌮", "🌯", "🍣", "🍜", "🍚", "🍟", "🍳", "🥞", "🥖",
  "🍰", "🍨", "🍪", "🍩", "☕", "🍵", "🥤", "🧃", "🍺", "🍷", "🍸",
];
