from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from models import BusinessAIProfile, Place
from askmycity.application.research_queue import ResearchQueue
from askmycity.domain.research import ResearchRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class KnowledgeBuilder:
    def __init__(self, session: Session):
        self.session = session
        self.queue = ResearchQueue(session)

    def enqueue_popular_unresearched(
        self,
        limit: int = 10,
        city: str | None = None,
    ) -> list[int]:
        researched_ids = select(BusinessAIProfile.place_id)
        statement = (
            select(Place)
            .where(Place.id.notin_(researched_ids))
            .order_by(
                Place.review_count.desc().nullslast(),
                Place.rating.desc().nullslast(),
            )
            .limit(limit)
        )
        if city:
            statement = statement.where(Place.city.ilike(f"%{city}%"))

        places = list(self.session.exec(statement).all())
        return self._enqueue_places(places, reason="popular_unresearched")

    def enqueue_stale(
        self,
        limit: int = 10,
        older_than_days: int = 30,
        city: str | None = None,
    ) -> list[int]:
        cutoff = utc_now() - timedelta(days=older_than_days)
        statement = (
            select(Place)
            .join(BusinessAIProfile, BusinessAIProfile.place_id == Place.id)
            .where(
                or_(
                    BusinessAIProfile.updated_at < cutoff,
                    BusinessAIProfile.updated_at.is_(None),
                )
            )
            .order_by(
                BusinessAIProfile.updated_at.asc().nullsfirst(),
                Place.review_count.desc().nullslast(),
            )
            .limit(limit)
        )
        if city:
            statement = statement.where(Place.city.ilike(f"%{city}%"))

        places = list(self.session.exec(statement).all())
        return self._enqueue_places(places, reason="stale_refresh")

    def enqueue_maintenance_batch(
        self,
        limit: int = 5,
        older_than_days: int = 30,
        city: str | None = None,
    ) -> list[int]:
        job_ids = self.enqueue_popular_unresearched(limit=limit, city=city)
        remaining = max(0, limit - len(job_ids))
        if remaining:
            job_ids.extend(
                self.enqueue_stale(
                    limit=remaining,
                    older_than_days=older_than_days,
                    city=city,
                )
            )
        return job_ids

    def _enqueue_places(self, places: list[Place], reason: str) -> list[int]:
        job_ids: list[int] = []
        for place in places:
            if place.id is None:
                continue
            job = self.queue.enqueue(
                ResearchRequest(
                    place_id=place.id,
                    reason=reason,
                    priority=50 if reason == "popular_unresearched" else 100,
                )
            )
            if job.id is not None and job.status == "queued":
                job_ids.append(job.id)
        return job_ids
