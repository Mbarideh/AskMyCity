import json
import time

from sqlmodel import Session

from ai_enrichment_service import enrich_place
from database import engine
from askmycity.application.knowledge_builder import KnowledgeBuilder
from askmycity.application.research_queue import ResearchQueue
from askmycity.core.config import settings
from askmycity.infrastructure.knowledge_repository import KnowledgeRepository


def _list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def run_once() -> bool:
    with Session(engine) as session:
        queue = ResearchQueue(session)

        if queue.completed_today() >= settings.knowledge_daily_limit:
            return False

        job = queue.claim_next()
        if not job:
            return False

        repository = KnowledgeRepository(session)
        place = repository.get_place(job.place_id)

        if not place:
            queue.fail(job, ValueError(f"Place {job.place_id} was not found"))
            return True

        try:
            data = enrich_place(
                place=place,
                use_web_search=True,
                requested_cuisine=job.requested_cuisine,
                requested_dishes=_list(job.requested_dishes_json),
                maximum_price=job.maximum_price,
            )
            repository.save_profile(place.id, data)
            matched = str(data.get("confidence", "low")).lower() in {
                "medium",
                "high",
            }
            queue.finish(job, matched=matched)
            print(
                f"Completed knowledge job {job.id} for {place.name}; "
                f"mode={data.get('enrichment_mode')}; matched={matched}"
            )
        except Exception as error:
            queue.fail(job, error)
            print(f"Knowledge job {job.id} failed: {error!r}")

        return True


def _refill_queue() -> int:
    with Session(engine) as session:
        queue = ResearchQueue(session)
        completed = queue.completed_today()
        remaining_today = max(0, settings.knowledge_daily_limit - completed)

        if remaining_today == 0:
            return 0

        batch_limit = min(
            settings.knowledge_auto_enqueue_size,
            remaining_today,
        )
        builder = KnowledgeBuilder(session)
        job_ids = builder.enqueue_maintenance_batch(
            limit=batch_limit,
            older_than_days=settings.knowledge_refresh_days,
            city=settings.knowledge_city or None,
        )
        return len(job_ids)


def run_forever() -> None:
    print("AskMyCity low-cost knowledge worker started.")
    print(
        "Configuration: "
        f"city={settings.knowledge_city or 'all'}, "
        f"daily_limit={settings.knowledge_daily_limit}, "
        f"refresh_days={settings.knowledge_refresh_days}"
    )

    while True:
        processed = 0

        for _ in range(settings.knowledge_worker_batch_size):
            if not run_once():
                break
            processed += 1

        if processed:
            continue

        queued = _refill_queue()
        if queued:
            print(f"Queued {queued} maintenance knowledge job(s).")
            continue

        time.sleep(settings.knowledge_poll_seconds)


if __name__ == "__main__":
    run_forever()
