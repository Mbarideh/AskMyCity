import json
import os
from functools import lru_cache
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


AI_MODEL = "gpt-5-mini"
MAX_CONVERSATION_MESSAGES = 20


AI_INSTRUCTIONS = (
    "You are AskMyCity's AI Query Planner. Convert the latest user "
    "message into precise structured local-search intent. "

    "MOST IMPORTANT CONTEXT RULE: Treat a complete new request as "
    "standalone and reset old cuisine, dish, category, budget, and city. "
    "Use conversation history only when the latest message is clearly a "
    "follow-up, for example: 'only cheaper ones', 'which one is closest?', "
    "'show me more', 'open now?', or 'what about Kanata?'. A complete request "
    "such as 'Where can I get homemade gnocchi under $25?' is standalone even "
    "when it follows an Iranian-restaurant search. Set context_mode to "
    "'follow_up' only for a true follow-up; otherwise use 'standalone'. "

    "CATEGORY: Return a simple singular category such as restaurant, plumber, "
    "dentist, tutor, mechanic, or cleaner. "

    "CUISINE: Normalize cuisine synonyms to a canonical value. Iranian food "
    "and Persian food both mean Persian cuisine. Use Italian, Persian, Indian, "
    "Japanese, etc. Do not put cuisine into the generic search field. "

    "DISHES: Extract specific requested foods or services as an array, including "
    "pasta, gnocchi, carbonara, kebab, ramen, tiramisu, and any other named item. "

    "CUISINE INFERENCE: When a dish has a strong, widely accepted cuisine association, "
    "use that cuisine to find candidates even if the user did not explicitly name it. "
    "Examples: gnocchi, carbonara, ravioli, lasagna, and tiramisu imply Italian; ramen "
    "implies Japanese; koobideh implies Persian. This is only candidate discovery and "
    "does not prove a restaurant serves the dish. "

    "BUDGET: Set budget_preference to affordable, moderate, or upscale when the "
    "user uses qualitative wording. Extract a numeric maximum_price from phrases "
    "such as under $25, below 40 dollars, or no more than $30. Preserve the "
    "currency amount exactly as a number; do not convert it. "

    "OTHER INTENT: Extract atmosphere terms, dietary requirements, open-now, "
    "language, rating, and review-count requirements. Dietary options are only "
    "food/diet requirements such as halal, kosher, vegan, vegetarian, or "
    "gluten-free. Never classify family-friendly, parking, patio, dine-in, "
    "takeout, delivery, reservations, Wi-Fi, or accessibility as dietary. "

    "CITY: Return only a city explicitly stated or clearly inherited in a true "
    "follow-up. Correct obvious spelling mistakes. Never invent a city. For near "
    "me without a city, return null because GPS is handled separately. "

    "SEARCH: Use only for a business name or a distinctive specialty not already "
    "represented by category, cuisine, dishes, atmosphere, dietary options, or "
    "language. Never copy the full request. "

    "ASSISTANT MESSAGE: Write one short friendly sentence confirming the planned "
    "search. Do not claim results were found. Do not mention JSON, SQL, database, "
    "prompts, or internal processing."
)

AI_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "askmycity_query_plan_v06",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "category": {"type": ["string", "null"]},
            "city": {"type": ["string", "null"]},
            "search": {"type": ["string", "null"]},
            "requested_cuisine": {"type": ["string", "null"]},
            "requested_dishes": {"type": "array", "items": {"type": "string"}},
            "budget_preference": {"type": ["string", "null"], "enum": ["affordable", "moderate", "upscale", None]},
            "maximum_price": {"type": ["number", "null"], "minimum": 0},
            "atmosphere": {"type": "array", "items": {"type": "string"}},
            "dietary_options": {"type": "array", "items": {"type": "string"}},
            "open_now": {"type": ["boolean", "null"]},
            "language": {"type": ["string", "null"]},
            "minimum_rating": {"type": ["number", "null"], "minimum": 0, "maximum": 5},
            "minimum_review_count": {"type": ["integer", "null"], "minimum": 0},
            "urgency": {"type": ["string", "null"], "enum": ["emergency", "urgent", "normal", None]},
            "context_mode": {"type": "string", "enum": ["standalone", "follow_up"]},
            "explanation": {"type": ["string", "null"]},
            "assistant_message": {"type": "string", "minLength": 1, "maxLength": 300}
        },
        "required": [
            "category", "city", "search", "requested_cuisine", "requested_dishes",
            "budget_preference", "maximum_price", "atmosphere", "dietary_options",
            "open_now", "language", "minimum_rating", "minimum_review_count",
            "urgency", "context_mode", "explanation", "assistant_message"
        ],
        "additionalProperties": False
    }
}

@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """
    Create one OpenAI client and reuse it for all requests
    handled by the current backend process.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from Backend/.env."
        )

    return OpenAI(
        api_key=api_key,
        timeout=20.0,
        max_retries=1,
    )


def normalize_optional_text(
    value: Any,
) -> str | None:
    """
    Convert empty or invalid text values to None.
    """

    if value is None:
        return None

    normalized_value = str(value).strip()

    if not normalized_value:
        return None

    return normalized_value


def normalize_minimum_rating(
    value: Any,
) -> float | None:
    """
    Convert a rating into a number between zero and five.
    """

    if value is None:
        return None

    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None

    return max(
        0.0,
        min(5.0, rating),
    )


def normalize_minimum_review_count(
    value: Any,
) -> int | None:
    """
    Convert a minimum review count into a non-negative
    integer.
    """

    if value is None:
        return None

    try:
        review_count = int(value)
    except (TypeError, ValueError):
        return None

    return max(0, review_count)


def remove_redundant_search(
    category: str | None,
    search: str | None,
) -> str | None:
    """
    Remove search when it merely repeats the category.
    """

    if not category or not search:
        return search

    normalized_category = (
        category.lower()
        .strip()
        .replace("-", " ")
    )

    normalized_search = (
        search.lower()
        .strip()
        .replace("-", " ")
    )

    category_words = {
        normalized_category,
        f"{normalized_category}s",
    }

    search_words = set(
        normalized_search.split()
    )

    if category_words.intersection(
        search_words
    ):
        return None

    return search


def normalize_urgency(
    value: Any,
) -> str:
    """
    Return one supported urgency value.
    """

    urgency = normalize_optional_text(
        value
    )

    if urgency:
        urgency = urgency.lower()

    allowed_urgencies = {
        "emergency",
        "urgent",
        "normal",
    }

    if urgency not in allowed_urgencies:
        return "normal"

    return urgency


def create_default_assistant_message(
    category: str | None,
    city: str | None,
    search: str | None,
    minimum_rating: float | None,
    minimum_review_count: int | None,
) -> str:
    """
    Create a safe fallback chat message if the model's
    assistant message is missing.
    """

    parts: list[str] = []

    if minimum_rating is not None:
        parts.append(
            f"rated {minimum_rating:g} or higher"
        )

    if minimum_review_count is not None:
        parts.append(
            f"with at least {minimum_review_count} reviews"
        )

    if search:
        parts.append(search)

    if category:
        parts.append(category)
    else:
        parts.append("local businesses")

    description = " ".join(parts)

    if city:
        return (
            f"I'll look for {description} in {city}."
        )

    return (
        f"I'll look for {description} near you."
    )


def normalize_ai_result(
    extracted: dict[str, Any],
) -> dict[str, Any]:
    """
    Clean and validate the model's structured response.
    """

    category = normalize_optional_text(
        extracted.get("category")
    )

    city = normalize_optional_text(
        extracted.get("city")
    )

    search = normalize_optional_text(
        extracted.get("search")
    )

    explanation = normalize_optional_text(
        extracted.get("explanation")
    )

    assistant_message = normalize_optional_text(
        extracted.get("assistant_message")
    )

    minimum_rating = normalize_minimum_rating(
        extracted.get("minimum_rating")
    )

    minimum_review_count = (
        normalize_minimum_review_count(
            extracted.get(
                "minimum_review_count"
            )
        )
    )

    urgency = normalize_urgency(
        extracted.get("urgency")
    )

    requested_cuisine = normalize_optional_text(extracted.get("requested_cuisine"))
    if requested_cuisine and requested_cuisine.lower() in {"iranian", "persian"}:
        requested_cuisine = "Persian"
    requested_dishes = [str(item).strip().lower() for item in (extracted.get("requested_dishes") or []) if str(item).strip()]
    budget_preference = normalize_optional_text(extracted.get("budget_preference"))
    maximum_price = extracted.get("maximum_price")
    try:
        maximum_price = float(maximum_price) if maximum_price is not None else None
    except (TypeError, ValueError):
        maximum_price = None
    atmosphere = [str(item).strip().lower() for item in (extracted.get("atmosphere") or []) if str(item).strip()]
    dietary_options = [str(item).strip().lower() for item in (extracted.get("dietary_options") or []) if str(item).strip()]
    open_now = extracted.get("open_now") if isinstance(extracted.get("open_now"), bool) else None
    language = normalize_optional_text(extracted.get("language"))
    context_mode = extracted.get("context_mode") if extracted.get("context_mode") in {"standalone", "follow_up"} else "standalone"

    if category:
        category = category.lower()

    search = remove_redundant_search(
        category=category,
        search=search,
    )

    if not assistant_message:
        assistant_message = (
            create_default_assistant_message(
                category=category,
                city=city,
                search=search,
                minimum_rating=minimum_rating,
                minimum_review_count=(
                    minimum_review_count
                ),
            )
        )

    return {
        "category": category,
        "city": city,
        "search": search,
        "minimum_rating": minimum_rating,
        "minimum_review_count": (
            minimum_review_count
        ),
        "requested_cuisine": requested_cuisine,
        "requested_dishes": requested_dishes,
        "budget_preference": budget_preference,
        "maximum_price": maximum_price,
        "atmosphere": atmosphere,
        "dietary_options": dietary_options,
        "open_now": open_now,
        "language": language,
        "context_mode": context_mode,
        "urgency": urgency,
        "explanation": explanation,
        "assistant_message": assistant_message,
    }


def normalize_conversation_messages(
    messages: list[Any] | None,
) -> list[dict[str, str]]:
    """
    Convert frontend conversation objects into safe
    OpenAI input messages.

    Supports dictionaries and SQLModel/Pydantic objects.
    """

    if not messages:
        return []

    normalized_messages: list[dict[str, str]] = []

    recent_messages = messages[
        -MAX_CONVERSATION_MESSAGES:
    ]

    for message in recent_messages:
        role: Any = None
        content: Any = None

        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        else:
            role = getattr(
                message,
                "role",
                None,
            )
            content = getattr(
                message,
                "content",
                None,
            )

        if role not in {
            "user",
            "assistant",
        }:
            continue

        normalized_content = (
            normalize_optional_text(content)
        )

        if not normalized_content:
            continue

        normalized_messages.append(
            {
                "role": role,
                "content": normalized_content[
                    :2000
                ],
            }
        )

    return normalized_messages


def build_ai_input(
    user_query: str,
    messages: list[Any] | None,
) -> list[dict[str, str]]:
    """
    Build conversation input and append the latest
    user message.

    The latest message is not appended twice when the
    frontend already included it in the history.
    """

    conversation = (
        normalize_conversation_messages(
            messages
        )
    )

    latest_message = {
        "role": "user",
        "content": user_query,
    }

    if not conversation:
        conversation.append(
            latest_message
        )

        return conversation

    final_message = conversation[-1]

    same_as_latest_query = (
        final_message["role"] == "user"
        and final_message["content"].strip()
        == user_query.strip()
    )

    if not same_as_latest_query:
        conversation.append(
            latest_message
        )

    return conversation[
        -MAX_CONVERSATION_MESSAGES:
    ]


def understand_search_query(
    user_query: str,
    messages: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Convert the latest message and conversation history
    into complete database search filters.
    """

    function_started_at = perf_counter()

    normalized_query = user_query.strip()

    if len(normalized_query) < 3:
        raise ValueError(
            "The search request is too short."
        )

    ai_input = build_ai_input(
        user_query=normalized_query,
        messages=messages,
    )

    client_started_at = perf_counter()

    client = get_openai_client()

    client_ready_at = perf_counter()

    ai_started_at = perf_counter()

    response = client.responses.create(
        model=AI_MODEL,
        instructions=AI_INSTRUCTIONS,
        input=ai_input,
        reasoning={
            "effort": "minimal",
        },
        text={
            "format": AI_RESPONSE_FORMAT,
        },
        max_output_tokens=600,
    )

    ai_finished_at = perf_counter()

    output_text = response.output_text

    if not output_text:
        raise RuntimeError(
            "The AI returned an empty response."
        )

    parsing_started_at = perf_counter()

    try:
        extracted = json.loads(
            output_text
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The AI returned invalid JSON."
        ) from error

    if not isinstance(extracted, dict):
        raise RuntimeError(
            "The AI returned an unexpected "
            "response format."
        )

    normalized_result = normalize_ai_result(
        extracted
    )

    function_finished_at = perf_counter()

    client_time = (
        client_ready_at
        - client_started_at
    )

    ai_time = (
        ai_finished_at
        - ai_started_at
    )

    parsing_time = (
        function_finished_at
        - parsing_started_at
    )

    total_time = (
        function_finished_at
        - function_started_at
    )

    print("")
    print(
        "====== CONVERSATIONAL AI TIMING ======"
    )
    print(
        f"History messages: "
        f"{len(ai_input) - 1}"
    )
    print(
        f"OpenAI client: {client_time:.3f} seconds"
    )
    print(
        f"OpenAI request: {ai_time:.3f} seconds"
    )
    print(
        f"JSON processing: {parsing_time:.3f} seconds"
    )
    print(
        f"AI service total: {total_time:.3f} seconds"
    )
    print(
        "======================================"
    )
    print("")

    return normalized_result