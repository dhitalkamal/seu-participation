"""Celery tasks for the participation service."""

from __future__ import annotations

from datetime import datetime, timezone

from celery import shared_task

from apps.participation.application.use_cases.promote_waitlist import (
    PromoteNextWaitlistUseCase,
)
from apps.participation.domain.repositories import IEventPublisher, IWaitlistRepository


def _expire_and_promote(
    *,
    waitlist_repo: IWaitlistRepository,
    publisher: IEventPublisher,
) -> None:
    """
    Remove stale offered entries and promote the next pending entry for each affected event.

    Extracted from the Celery task so it can be tested without Django/Celery setup.

    @param waitlist_repo - repository providing list_offered_before and remove
    @param publisher - domain event publisher for waitlist.promoted events
    """
    now = datetime.now(timezone.utc)
    stale_entries = waitlist_repo.list_offered_before(now)

    # track which events had a slot freed to avoid double-promoting
    affected_events: set = set()
    for entry in stale_entries:
        waitlist_repo.remove(entry.id)
        affected_events.add(entry.event_id)

    for event_id in affected_events:
        PromoteNextWaitlistUseCase(waitlist_repo=waitlist_repo, publisher=publisher).execute(
            event_id=event_id
        )


@shared_task(name="apps.participation.tasks.expire_stale_offers")
def expire_stale_offers() -> None:
    """Celery beat task: expire overdue waitlist offers and promote next-in-queue."""
    from apps.participation.infrastructure.publisher import RabbitMQEventPublisher
    from apps.participation.infrastructure.repositories import DjangoWaitlistRepository

    _expire_and_promote(
        waitlist_repo=DjangoWaitlistRepository(),
        publisher=RabbitMQEventPublisher(),
    )
