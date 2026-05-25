"""Use case: promote the next pending waitlist entry to 'offered' status."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from apps.participation.domain.repositories import (
    IEventPublisher,
    IWaitlistRepository,
)

# ! acceptance window enforced here and checked in AcceptWaitlistOfferUseCase
_OFFER_WINDOW_HOURS = 24


class PromoteNextWaitlistUseCase:
    """Set the next pending waitlist entry to offered, starting a 24h acceptance window."""

    def __init__(
        self,
        waitlist_repo: IWaitlistRepository,
        publisher: IEventPublisher,
    ) -> None:
        self._waitlist = waitlist_repo
        self._publisher = publisher

    def execute(self, *, event_id: uuid.UUID) -> None:
        """
        Promote the lowest-position pending entry for the event.

        Sets status=offered, offered_at=now, expires_at=now+24h, then publishes
        participation.waitlist.promoted. Does nothing if no pending entry exists.

        @param event_id - the event whose waitlist to advance
        """
        entry = self._waitlist.next_pending_in_queue(event_id)
        if entry is None:
            return

        now = datetime.now(timezone.utc)
        entry.status = "offered"
        entry.offered_at = now
        entry.expires_at = now + timedelta(hours=_OFFER_WINDOW_HOURS)
        self._waitlist.update(entry)

        self._publisher.publish(
            routing_key="participation.waitlist.promoted",
            payload={
                "user_id": str(entry.user_id),
                "event_id": str(event_id),
                "entry_id": str(entry.id),
            },
        )
