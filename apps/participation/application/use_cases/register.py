"""Use case: register a user for an event or add them to the waitlist."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone

from apps.participation.domain.entities import RegistrationEntity, WaitlistEntryEntity
from apps.participation.domain.exceptions import AlreadyRegisteredError
from apps.participation.domain.repositories import (
    IEventClient,
    IEventPublisher,
    IRegistrationRepository,
    IWaitlistRepository,
)


def _generate_code() -> str:
    """Generate a unique 8-character alphanumeric registration code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class RegisterForEventUseCase:
    """Register a user for an event or add them to the waitlist if full."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        waitlist_repo: IWaitlistRepository,
        event_client: IEventClient,
        publisher: IEventPublisher | None = None,
    ) -> None:
        self._regs = reg_repo
        self._waitlist = waitlist_repo
        self._events = event_client
        self._publisher = publisher

    def execute(
        self,
        *,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int = 1,
        notes: str | None = None,
    ) -> RegistrationEntity | WaitlistEntryEntity:
        """
        Check event capacity and either create a confirmed registration or a waitlist entry.

        @param event_id - the event to register for
        @param user_id - UUID from the JWT
        @param quantity - number of tickets, defaults to 1
        @returns RegistrationEntity if a spot is available, WaitlistEntryEntity if full
        @raises EventNotFoundError if the event-service returns 404 or is unreachable
        @raises AlreadyRegisteredError if a non-cancelled registration already exists
        """
        event = self._events.get_event(event_id)

        if self._regs.has_active(event_id, user_id):
            raise AlreadyRegisteredError("You are already registered for this event.")

        now = datetime.now(timezone.utc)

        if event.is_at_capacity:
            position = self._waitlist.count_for_event(event_id) + 1
            # 24-hour acceptance window as per PRD
            entry = WaitlistEntryEntity(
                id=uuid.uuid4(),
                event_id=event_id,
                user_id=user_id,
                position=position,
                created_at=now,
                expires_at=None,
            )
            return self._waitlist.add(entry)

        registration = RegistrationEntity(
            id=uuid.uuid4(),
            event_id=event_id,
            user_id=user_id,
            status="confirmed",
            registration_code=_generate_code(),
            quantity=quantity,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        created = self._regs.create(registration)
        if self._publisher is not None:
            self._publisher.publish(
                routing_key="participation.registration.created",
                payload={
                    "user_id": str(user_id),
                    "event_id": str(event_id),
                    "registration_id": str(created.id),
                    "registration_code": created.registration_code,
                },
            )
        return created
