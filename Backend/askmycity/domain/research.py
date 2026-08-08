from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ResearchRequest:
    place_id: int
    requested_cuisine: str | None = None
    requested_dishes: list[str] = field(default_factory=list)
    maximum_price: float | None = None
    priority: int = 100
    reason: str = "knowledge_builder"


@dataclass(frozen=True)
class ResearchOutcome:
    place_id: int
    status: str
    matched: bool
    started_at: datetime
    finished_at: datetime
    error_message: str | None = None
