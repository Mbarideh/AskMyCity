# AskMyCity – Amenities & Services update

This build adds a visual Amenities & Services section to **My Business** and persists it to PostgreSQL.

## Saved fields

The owner can save structured values for:

- Service: dine-in, takeout, delivery, catering, reservations
- Parking: free, paid, street
- Seating: indoor, patio/outdoor
- Accessibility: entrance, seating, washroom
- Family: kids menu, high chairs, family-friendly
- Amenities: Wi-Fi, washroom, charging outlets
- Payments: credit, debit, cash, contactless
- Halal status: fully halal / halal options / not halal / unknown
- Halal verification URL and certificate/note
- Alcohol status: none / beer & wine / full bar / served / unknown
- Dietary: vegetarian / vegan / gluten-free

## Database behavior

A new `business_profiles.amenities_json` TEXT column is created automatically at backend startup with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

When a Business Studio profile is saved, the same structured data is also merged into the customer-facing `places.features_json` under:

```json
{
  "owner_provided": {
    "source": "business_owner",
    "updated_at": "...",
    "data": { ... }
  }
}
```

Existing imported/enriched `places.features_json` data is preserved.

## Verification SQL

```sql
SELECT id, display_name, amenities_json
FROM business_profiles
ORDER BY id DESC
LIMIT 5;
```

```sql
SELECT id, name, features_json
FROM places
WHERE source = 'business_studio'
ORDER BY id DESC
LIMIT 5;
```
