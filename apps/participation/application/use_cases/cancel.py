"""Use case: cancel an existing registration and promote the next waitlist entry."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.application.use_cases.register import _generate_code
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
    """Cancel a registration and promote the next person in the waitlist."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        waitlist_repo: IWaitlistRepository,
        publisher: IEventPublisher | None = None,
    ) -> None:
        self._regs = reg_repo
        self._waitlist = waitlist_repo
        self._publisher = publisher

    def execute(self, *, registration_id: uuid.UUID, user_id: uuid.UUID) -> RegistrationEntity:
        """
        Validate ownership and status, then cancel and optionally promote a waitlist entry.

        @param registration_id - the registration to cancel
        @param user_id - UUID from JWT; must match registration.user_id
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

        next_entry = self._waitlist.next_in_queue(registration.event_id)
        if next_entry is not None:
            self._waitlist.remove(next_entry.id)
            promoted = RegistrationEntity(
                id=uuid.uuid4(),
                event_id=registration.event_id,
                user_id=next_entry.user_id,
                status="confirmed",
                registration_code=_generate_code(),
                quantity=1,
                created_at=now,
                updated_at=now,
            )
            self._regs.create(promoted)
            if self._publisher is not None:
                self._publisher.publish(
                    routing_key="participation.waitlist.promoted",
                    payload={
                        "user_id": str(next_entry.user_id),
                        "event_id": str(registration.event_id),
                        "registration_id": str(promoted.id),
                        "registration_code": promoted.registration_code,
                    },
                )

        return registration
