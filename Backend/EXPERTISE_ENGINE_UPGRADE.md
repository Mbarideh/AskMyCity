# AskMyCity v5.0 — Expertise Engine

The Expertise Engine separates **specialization** from rating, popularity, and distance.

For a burger request, evidence is weighted in this order:

1. Dedicated category such as `Hamburger restaurant`
2. Burger identity in the business name
3. Breadth of verified official menu items
4. Positive dish reputation and verified AI profile
5. Broad cuisine relationship (weak discovery signal only)

Results with a requested dish are ranked by expertise first, then overall match,
distance, rating, and review count. Existing API fields remain unchanged; these
optional fields are added to each result:

- `expertise_score`
- `expertise_level`
- `expertise_reasons`
