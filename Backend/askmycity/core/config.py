from dataclasses import dataclass
import os


def _int(name: str, default: int, minimum: int = 1, maximum: int = 10000) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    # On-demand search controls.
    research_batch_size: int = _int("AI_RESEARCH_BATCH_SIZE", 1, 1, 2)
    research_max_candidates: int = _int("AI_RESEARCH_MAX_CANDIDATES", 1, 1, 5)
    research_target_results: int = _int("AI_RESEARCH_TARGET_RESULTS", 1, 1, 2)

    # Background knowledge builder controls.
    knowledge_worker_batch_size: int = _int("KNOWLEDGE_WORKER_BATCH_SIZE", 1, 1, 10)
    knowledge_auto_enqueue_size: int = _int("KNOWLEDGE_AUTO_ENQUEUE_SIZE", 3, 1, 25)
    knowledge_daily_limit: int = _int("KNOWLEDGE_DAILY_LIMIT", 20, 1, 1000)
    knowledge_refresh_days: int = _int("KNOWLEDGE_REFRESH_DAYS", 30, 1, 365)
    knowledge_poll_seconds: int = _int("KNOWLEDGE_POLL_SECONDS", 15, 2, 3600)
    knowledge_city: str = os.getenv("KNOWLEDGE_CITY", "Ottawa").strip()


settings = Settings()
