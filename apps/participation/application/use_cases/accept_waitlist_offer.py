"""Use case: accept a waitlist offer within the 24h window."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.application.use_cases.register import _generate_code
from apps.participation.domain.entities import RegistrationEntity
from apps.participation.domain.exceptions import (
    WaitlistOfferAlreadyRespondedError,
    WaitlistOfferExpiredError,
    WaitlistOfferNotFoundError,
)
from apps.participation.domain.repositories import (
    IEventPublisher,
    IRegistrationRepository,
    IWaitlistRepository,
)


class AcceptWaitlistOfferUseCase:
    """Convert an offered waitlist entry into a confirmed registration."""

    def __init__(
        self,
        waitlist_repo: IWaitlistRepository,
        reg_repo: IRegistrationRepository,
        publisher: IEventPublisher,
    ) -> None:
        self._waitlist = waitlist_repo
        self._regs = reg_repo
        self._publisher = publisher

    def execute(self, *, entry_id: uuid.UUID, user_id: uuid.UUID) -> RegistrationEntity:
        """
        Accept the offer and create a confirmed registration.

        @param entry_id - the waitlist entry UUID
        @param user_id - must match entry.user_id to prevent cross-user acceptance
        @returns the newly created confirmed RegistrationEntity
        @raises WaitlistOfferNotFoundError if entry absent or owned by another user
        @raises WaitlistOfferExpiredError if acceptance window has passed
        @raises WaitlistOfferAlreadyRespondedError if entry is not in offered status
        """
        entry = self._waitlist.get_by_id(entry_id)

        # * hide existence from wrong users, same error as not found
        if entry is None or entry.user_id != user_id:
            raise WaitlistOfferNotFoundError("Waitlist offer not found.")

        # ! only offered entries can be accepted; pending means promotion hasn't happened
        if entry.status != "offered":
            raise WaitlistOfferAlreadyRespondedError("This offer is not in an acceptable state.")

        now = datetime.now(timezone.utc)
        if entry.expires_at is not None and entry.expires_at <= now:
            raise WaitlistOfferExpiredError("The acceptance window has expired.")

        self._waitlist.remove(entry_id)

        registration = RegistrationEntity(
            id=uuid.uuid4(),
            event_id=entry.event_id,
            user_id=user_id,
            status="confirmed",
            registration_code=_generate_code(),
            quantity=1,
            created_at=now,
            updated_at=now,
        )
        self._regs.create(registration)

        self._publisher.publish(
            routing_key="participation.waitlist.accepted",
            payload={
                "user_id": str(user_id),
                "event_id": str(entry.event_id),
                "registration_id": str(registration.id),
                "registration_code": registration.registration_code,
            },
        )

        return registration
