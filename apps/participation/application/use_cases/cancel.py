"""Use case: cancel an existing registration and promote the next waitlist entry."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.application.use_cases.promote_waitlist import (
    PromoteNextWaitlistUseCase,
)
from apps.participation.domain.entities import RegistrationEntity
from apps.participation.domain.exceptions import (
    InvalidRegistrationStatusError,
    RegistrationNotFoundError,
)
from apps.participation.domain.repositories import (
    IEventPublisher,
    IRegistrationRepository,
    IWaitlistRepository,
)

# ! exactly these statuses are cancellable, no others
_CANCELLABLE: frozenset[str] = frozenset({"pending", "confirmed", "waitlisted"})


class CancelRegistrationUseCase:
    """Cancel a registration and offer the freed slot to the next person in the waitlist."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        waitlist_repo: IWaitlistRepository,
        publisher: IEventPublisher | None = None,
    ) -> None:
        self._regs = reg_repo
        self._waitlist = waitlist_repo
        self._publisher = publisher

    def execute(
        self, *, registration_id: uuid.UUID, user_id: uuid.UUID, email: str = ""
    ) -> RegistrationEntity:
        """
        Validate ownership and status, then cancel and offer slot to next waitlist entry.

        @param registration_id - the registration to cancel
        @param user_id - UUID from JWT; must match registration.user_id
        @param email - user email from JWT claims, forwarded to domain events for notifications
        @returns the cancelled RegistrationEntity
        @raises RegistrationNotFoundError if not found or not owned by user
        @raises InvalidRegistrationStatusError if status is not cancellable
        """
        registration = self._regs.get_by_id(registration_id)

        # * raise not-found rather than forbidden to avoid leaking registration existence
        if registration.user_id != user_id:
            raise RegistrationNotFoundError("Registration not found.")

        if registration.status not in _CANCELLABLE:
            raise InvalidRegistrationStatusError(
                f"Cannot cancel a registration with status '{registration.status}'."
            )

        now = datetime.now(timezone.utc)
        registration.status = "cancelled"
        registration.cancelled_at = now
        registration.updated_at = now
        self._regs.update(registration)

        # * promote the next pending waitlist entry to offered (24h acceptance window)
        if self._publisher is not None:
            PromoteNextWaitlistUseCase(
                waitlist_repo=self._waitlist, publisher=self._publisher
            ).execute(event_id=registration.event_id)

        if self._publisher is not None:
            self._publisher.publish(
                routing_key="participation.registration.cancelled",
                payload={
                    "user_id": str(user_id),
                    "event_id": str(registration.event_id),
                    "registration_id": str(registration_id),
                    "registration_code": registration.registration_code,
                    "email": email,
                },
            )

        return registration
