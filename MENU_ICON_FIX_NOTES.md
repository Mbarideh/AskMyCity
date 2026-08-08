# AskMyCity Menu Icon Fix

This release restores meaningful menu icons across Business Studio and the public restaurant page.

## What changed
- Menu items now have a persistent optional `icon` field in PostgreSQL.
- Existing menu rows are automatically backfilled with sensible icons when the backend starts.
- New manually-created and imported menu items automatically receive an icon when one is not supplied.
- Business Studio shows each item's icon and includes an icon preview/selector when adding an item.
- Public restaurant menus show item-specific icons when no food photo exists.
- Public menu category headings also show category icons.
- The Business Studio Menu navigation uses a food/menu icon instead of the old generic list glyph.

## Examples
- New York Steak -> 🥩
- Grilled Salmon -> 🐟
- Chicken Parmesan -> 🍗
- Lasagna / Fettuccine / Spaghetti -> 🍝
- Cappuccino / Espresso -> ☕
- Soda -> 🥤
- Cheesecake / Tiramisu -> 🍰

The backend migration is additive and runs with `ADD COLUMN IF NOT EXISTS`, so existing data is preserved.
