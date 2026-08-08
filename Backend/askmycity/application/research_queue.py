import json
from datetime import datetime, time, timezone

from sqlmodel import Session, select

from models import KnowledgeResearchJob
from askmycity.domain.research import ResearchRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ResearchQueue:
    def __init__(self, session: Session):
        self.session = session

    def enqueue(self, request: ResearchRequest) -> KnowledgeResearchJob:
        target_key = json.dumps(
            {
                "cuisine": request.requested_cuisine,
                "dishes": sorted(d.lower() for d in request.requested_dishes),
                "maximum_price": request.maximum_price,
            },
            sort_keys=True,
        )

        existing = self.session.exec(
            select(KnowledgeResearchJob).where(
                KnowledgeResearchJob.place_id == request.place_id,
                KnowledgeResearchJob.target_key == target_key,
                KnowledgeResearchJob.status.in_(["queued", "running", "completed"]),
            )
        ).first()
        if existing:
            return existing

        job = KnowledgeResearchJob(
            place_id=request.place_id,
            target_key=target_key,
            requested_cuisine=request.requested_cuisine,
            requested_dishes_json=json.dumps(request.requested_dishes),
            maximum_price=request.maximum_price,
            priority=request.priority,
            reason=request.reason,
            status="queued",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def claim_next(self) -> KnowledgeResearchJob | None:
        job = self.session.exec(
            select(KnowledgeResearchJob)
            .where(KnowledgeResearchJob.status == "queued")
            .order_by(
                KnowledgeResearchJob.priority.asc(),
                KnowledgeResearchJob.created_at.asc(),
            )
        ).first()
        if not job:
            return None

        job.status = "running"
        job.started_at = utc_now()
        job.updated_at = utc_now()
        job.attempt_count += 1
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def finish(self, job: KnowledgeResearchJob, matched: bool) -> None:
        job.status = "completed"
        job.matched = matched
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        job.error_message = None
        self.session.add(job)
        self.session.commit()

    def fail(self, job: KnowledgeResearchJob, error: Exception) -> None:
        job.status = "failed"
        job.error_message = str(error)[:2000]
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        self.session.add(job)
        self.session.commit()

    def retry_failed(self, limit: int = 10, max_attempts: int = 2) -> int:
        jobs = list(
            self.session.exec(
                select(KnowledgeResearchJob)
                .where(
                    KnowledgeResearchJob.status == "failed",
                    KnowledgeResearchJob.attempt_count < max_attempts,
                )
                .order_by(KnowledgeResearchJob.updated_at.asc())
                .limit(limit)
            ).all()
        )
        for job in jobs:
            job.status = "queued"
            job.error_message = None
            job.finished_at = None
            job.updated_at = utc_now()
            self.session.add(job)
        if jobs:
            self.session.commit()
        return len(jobs)

    def completed_today(self) -> int:
        today = utc_now().date()
        start = datetime.combine(today, time.min)
        return len(
            list(
                self.session.exec(
                    select(KnowledgeResearchJob.id).where(
                        KnowledgeResearchJob.status == "completed",
                        KnowledgeResearchJob.finished_at >= start,
                    )
                ).all()
            )
        )
