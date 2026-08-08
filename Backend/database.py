import os
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from fastapi import FastAPI
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine


POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = quote_plus(os.getenv("POSTGRES_PASSWORD", "Mb654321@"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "askmycity")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    ),
)

engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    with Session(engine) as session:
        yield session


def _add_place_columns() -> None:
    columns = {
        "google_id": "TEXT",
        "cid": "TEXT",
        "business_type": "TEXT",
        "subtypes": "TEXT",
        "street": "TEXT",
        "county": "TEXT",
        "time_zone": "TEXT",
        "reviews_1_star": "INTEGER",
        "reviews_2_star": "INTEGER",
        "reviews_3_star": "INTEGER",
        "reviews_4_star": "INTEGER",
        "reviews_5_star": "INTEGER",
        "reviews_link": "TEXT",
        "photo_url": "TEXT",
        "logo_url": "TEXT",
        "street_view_url": "TEXT",
        "business_status": "TEXT",
        "price_range": "TEXT",
        "working_hours_json": "TEXT",
        "other_hours_json": "TEXT",
        "features_json": "TEXT",
        "reservation_links": "TEXT",
        "menu_link": "TEXT",
        "order_links": "TEXT",
        "source": "VARCHAR(50) NOT NULL DEFAULT 'manual'",
        "source_query": "TEXT",
        "imported_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with engine.begin() as connection:
        for name, data_type in columns.items():
            connection.execute(
                text(
                    f"ALTER TABLE places ADD COLUMN IF NOT EXISTS "
                    f"{name} {data_type}"
                )
            )

        indexes = [
            ("ix_places_google_id", "google_id"),
            ("ix_places_cid", "cid"),
            ("ix_places_business_type", "business_type"),
            ("ix_places_source", "source"),
        ]
        for index_name, column_name in indexes:
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON places ({column_name})"
                )
            )



def _add_ai_profile_columns() -> None:
    columns = {
        "cuisine_confidence": "VARCHAR(20) NOT NULL DEFAULT 'low'",
        "menu_items_json": "TEXT",
        "menu_confidence": "VARCHAR(20) NOT NULL DEFAULT 'low'",
        "dish_reputation_json": "TEXT",
        "price_level": "VARCHAR(30)",
        "average_main_price_cad": "DOUBLE PRECISION",
        "price_confidence": "VARCHAR(20) NOT NULL DEFAULT 'low'",
        "value_for_money": "VARCHAR(20)",
    }
    with engine.begin() as connection:
        for name, data_type in columns.items():
            connection.execute(text(
                f"ALTER TABLE business_ai_profiles ADD COLUMN IF NOT EXISTS {name} {data_type}"
            ))
        for index_name, column_name in [
            ("ix_business_ai_profiles_cuisine_confidence", "cuisine_confidence"),
            ("ix_business_ai_profiles_menu_confidence", "menu_confidence"),
            ("ix_business_ai_profiles_price_level", "price_level"),
            ("ix_business_ai_profiles_price_confidence", "price_confidence"),
            ("ix_business_ai_profiles_value_for_money", "value_for_money"),
        ]:
            connection.execute(text(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON business_ai_profiles ({column_name})"
            ))



def _add_business_profile_columns() -> None:
    columns = {
        "amenities_json": "TEXT",
    }
    with engine.begin() as connection:
        for name, data_type in columns.items():
            connection.execute(text(
                f"ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS {name} {data_type}"
            ))


def _add_menu_item_columns() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS icon VARCHAR(16)"
        ))
        # Backfill existing items once so legacy menus immediately get useful icons.
        connection.execute(text(
            """
            UPDATE menu_items
            SET icon = CASE
                WHEN lower(coalesce(name, '')) ~ '(cappuccino|espresso|latte|coffee|americano|macchiato|mocha)' THEN '☕'
                WHEN lower(coalesce(name, '')) ~ '(tea|chai|matcha)' THEN '🍵'
                WHEN lower(coalesce(name, '')) ~ '(soda|cola|coke|pepsi)' THEN '🥤'
                WHEN lower(coalesce(name, '')) ~ '(juice|lemonade|smoothie|shake)' THEN '🧃'
                WHEN lower(coalesce(name, '')) ~ '(steak|beef|ribeye|sirloin)' THEN '🥩'
                WHEN lower(coalesce(name, '')) ~ '(salmon|fish|cod|tuna|trout|tilapia)' THEN '🐟'
                WHEN lower(coalesce(name, '')) ~ '(chicken|wings)' THEN '🍗'
                WHEN lower(coalesce(name, '')) ~ '(burger|cheeseburger|hamburger)' THEN '🍔'
                WHEN lower(coalesce(name, '')) ~ '(pizza|pepperoni|margherita)' THEN '🍕'
                WHEN lower(coalesce(name, '')) ~ '(spaghetti|pasta|lasagna|fettuccine|linguine|ravioli|penne|alfredo|marinara)' THEN '🍝'
                WHEN lower(coalesce(name, '')) ~ '(salad|caesar)' THEN '🥗'
                WHEN lower(coalesce(name, '')) ~ '(soup|chowder|bisque)' THEN '🍲'
                WHEN lower(coalesce(name, '')) ~ '(sandwich|panini|wrap)' THEN '🥪'
                WHEN lower(coalesce(name, '')) ~ '(taco)' THEN '🌮'
                WHEN lower(coalesce(name, '')) ~ '(burrito|quesadilla)' THEN '🌯'
                WHEN lower(coalesce(name, '')) ~ '(sushi|sashimi|nigiri|maki)' THEN '🍣'
                WHEN lower(coalesce(name, '')) ~ '(ramen|noodle|pho)' THEN '🍜'
                WHEN lower(coalesce(name, '')) ~ '(fries|poutine)' THEN '🍟'
                WHEN lower(coalesce(name, '')) ~ '(breakfast|egg|omelet)' THEN '🍳'
                WHEN lower(coalesce(name, '')) ~ '(pancake|waffle|crepe)' THEN '🥞'
                WHEN lower(coalesce(name, '')) ~ '(cheesecake|tiramisu|cake|pie)' THEN '🍰'
                WHEN lower(coalesce(name, '')) ~ '(ice cream|gelato|sorbet)' THEN '🍨'
                WHEN lower(coalesce(name, '')) ~ '(cookie)' THEN '🍪'
                WHEN lower(coalesce(category, '')) ~ '(dessert)' THEN '🍰'
                WHEN lower(coalesce(category, '')) ~ '(beverage|drink)' THEN '🥤'
                WHEN lower(coalesce(category, '')) ~ '(pasta)' THEN '🍝'
                WHEN lower(coalesce(category, '')) ~ '(salad)' THEN '🥗'
                ELSE '🍴'
            END
            WHERE icon IS NULL OR btrim(icon) = ''
            """
        ))

def create_database_tables():
    SQLModel.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS account_type
                VARCHAR(30) NOT NULL DEFAULT 'customer'
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS business_name VARCHAR(200)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_users_account_type
                ON users (account_type)
                """
            )
        )

    _add_place_columns()
    _add_ai_profile_columns()
    _add_business_profile_columns()
    _add_menu_item_columns()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_database_tables()
    yield
