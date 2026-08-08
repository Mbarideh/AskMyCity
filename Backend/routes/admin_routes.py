from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from askmycity.application.knowledge_builder import KnowledgeBuilder
from askmycity.application.research_queue import ResearchQueue
from askmycity.core.config import settings
from database import get_session
from models import BusinessAIProfile, KnowledgeResearchJob, Place

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/knowledge/summary")
def knowledge_summary(session: Session = Depends(get_session)):
    total_places = session.exec(select(func.count()).select_from(Place)).one()
    total_profiles = session.exec(
        select(func.count()).select_from(BusinessAIProfile)
    ).one()

    counts = {}
    for status in ("queued", "running", "completed", "failed"):
        counts[status] = session.exec(
            select(func.count())
            .select_from(KnowledgeResearchJob)
            .where(KnowledgeResearchJob.status == status)
        ).one()

    coverage = round((total_profiles / total_places * 100), 2) if total_places else 0
    completed_today = ResearchQueue(session).completed_today()

    return {
        "total_places": total_places,
        "knowledge_profiles": total_profiles,
        "coverage_percent": coverage,
        "completed_today": completed_today,
        "daily_limit": settings.knowledge_daily_limit,
        "remaining_today": max(
            0, settings.knowledge_daily_limit - completed_today
        ),
        "jobs": counts,
        "configuration": {
            "city": settings.knowledge_city or None,
            "refresh_days": settings.knowledge_refresh_days,
            "auto_enqueue_size": settings.knowledge_auto_enqueue_size,
        },
    }


@router.post("/knowledge/enqueue-popular")
def enqueue_popular(
    limit: int = Query(default=5, ge=1, le=25),
    city: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    job_ids = KnowledgeBuilder(session).enqueue_popular_unresearched(
        limit=limit,
        city=city,
    )
    return {"queued": len(job_ids), "job_ids": job_ids}


@router.post("/knowledge/enqueue-stale")
def enqueue_stale(
    limit: int = Query(default=5, ge=1, le=25),
    older_than_days: int = Query(default=30, ge=1, le=365),
    city: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    job_ids = KnowledgeBuilder(session).enqueue_stale(
        limit=limit,
        older_than_days=older_than_days,
        city=city,
    )
    return {"queued": len(job_ids), "job_ids": job_ids}


@router.post("/knowledge/enqueue-maintenance")
def enqueue_maintenance(
    limit: int = Query(default=5, ge=1, le=25),
    older_than_days: int = Query(default=30, ge=1, le=365),
    city: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    job_ids = KnowledgeBuilder(session).enqueue_maintenance_batch(
        limit=limit,
        older_than_days=older_than_days,
        city=city,
    )
    return {"queued": len(job_ids), "job_ids": job_ids}


@router.post("/knowledge/retry-failed")
def retry_failed(
    limit: int = Query(default=5, ge=1, le=25),
    session: Session = Depends(get_session),
):
    retried = ResearchQueue(session).retry_failed(limit=limit)
    return {"retried": retried}


@router.get("/knowledge/jobs")
def list_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return list(
        session.exec(
            select(KnowledgeResearchJob)
            .order_by(KnowledgeResearchJob.created_at.desc())
            .limit(limit)
        ).all()
    )
