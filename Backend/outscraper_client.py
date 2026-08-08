import os
from typing import Any

import requests


API_URL = "https://api.outscraper.com/google-maps-search"


class OutscraperError(RuntimeError):
    pass


def search_places(
    *,
    query: str,
    limit: int = 100,
    language: str = "en",
    region: str = "CA",
    allow_paid_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetch future categories/cities from Outscraper.

    Ottawa restaurants are intentionally blocked because the paid XLSX file
    is already included in this project. Set allow_paid_refresh=True only
    when you deliberately want to purchase a fresh copy later.
    """
    normalized = query.casefold()
    if (
        "restaurant" in normalized
        and "ottawa" in normalized
        and not allow_paid_refresh
    ):
        raise OutscraperError(
            "Ottawa restaurants are already purchased. Import the included "
            "XLSX file instead of paying for the same dataset again."
        )

    api_key = os.getenv("OUTSCRAPER_API_KEY")
    if not api_key:
        raise OutscraperError(
            "OUTSCRAPER_API_KEY is missing from the .env/environment."
        )

    response = requests.get(
        API_URL,
        headers={"X-API-KEY": api_key},
        params={
            "query": query,
            "limit": limit,
            "language": language,
            "region": region,
            "async": "false",
        },
        timeout=180,
    )

    if response.status_code >= 400:
        raise OutscraperError(
            f"Outscraper returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    payload = response.json()
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        raise OutscraperError("Unexpected Outscraper response format.")

    if data and isinstance(data[0], list):
        return data[0]
    return data
