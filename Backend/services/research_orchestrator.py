"""AskMyCity live-research orchestration boundaries.

The live endpoint currently delegates to the stable orchestration implementation
in routes.ai_routes. This module documents the service boundary used by Backend
2.0 and provides reusable cache policy helpers. Keeping policy here prevents the
API route from becoming the permanent home of research logic.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ResearchPolicy:
    batch_size: int = 3
    maximum_candidates: int = 12
    target_matches: int = 3
    positive_ttl: timedelta = timedelta(days=30)
    negative_ttl: timedelta = timedelta(days=1)
    failed_retry_after: timedelta = timedelta(minutes=15)


def cache_is_fresh(*, researched_at: datetime | None, matched: bool, now: datetime, policy: ResearchPolicy) -> bool:
    if researched_at is None:
        return False
    ttl = policy.positive_ttl if matched else policy.negative_ttl
    return now - researched_at <= ttl
