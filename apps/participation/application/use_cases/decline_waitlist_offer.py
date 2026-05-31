"""Use case: decline a waitlist offer, freeing the slot for the next person."""

from __future__ import annotations

import uuid

from apps.participation.application.use_cases.promote_waitlist import PromoteNextWaitlistUseCase
from apps.participation.domain.exceptions import (
    WaitlistOfferAlreadyRespondedError,
    WaitlistOfferNotFoundError,
)
from apps.participation.domain.repositories import (
    IEventPublisher,
    IWaitlistRepository,
)


class DeclineWaitlistOfferUseCase:
    """Remove an offered waitlist entry when the user explicitly declines."""

    def __init__(
        self,
        waitlist_repo: IWaitlistRepository,
        publisher: IEventPublisher,
    ) -> None:
        self._waitlist = waitlist_repo
        self._publisher = publisher

    def execute(self, *, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Decline the offer, remove the entry, and promote the next person.

        @param entry_id - the waitlist entry UUID
        @param user_id - must match entry.user_id to prevent cross-user action
        @raises WaitlistOfferNotFoundError if entry absent or owned by another user
        @raises WaitlistOfferAlreadyRespondedError if entry is not in offered status
        """
        entry = self._waitlist.get_by_id(entry_id)

        if entry is None or entry.user_id != user_id:
            raise WaitlistOfferNotFoundError("Waitlist offer not found.")

        # ! only offered entries can be declined; pending means not yet promoted
        if entry.status != "offered":
            raise WaitlistOfferAlreadyRespondedError("This offer is not in a declinable state.")

        event_id = entry.event_id
        self._waitlist.remove(entry_id)

        self._publisher.publish(
            routing_key="participation.waitlist.declined",
            payload={
                "user_id": str(user_id),
                "event_id": str(event_id),
                "entry_id": str(entry_id),
            },
        )

        PromoteNextWaitlistUseCase(waitlist_repo=self._waitlist, publisher=self._publisher).execute(
            event_id=event_id
        )
