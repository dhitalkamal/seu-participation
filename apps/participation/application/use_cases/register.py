"""Use case: register a user for an event or add them to the waitlist."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from apps.participation.domain.entities import RegistrationEntity, WaitlistEntryEntity
from apps.participation.domain.exceptions import AlreadyRegisteredError, ParticipationConflictError
from apps.participation.domain.repositories import (
    IEventClient,
    IEventPublisher,
    IParticipationContextRepository,
    IRegistrationRepository,
    IWaitlistRepository,
)

# ! waitlist slots expire after 24 hours  - promoted user must act within this window
_WAITLIST_EXPIRY_HOURS = 24


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
        context_repo: IParticipationContextRepository | None = None,
    ) -> None:
        self._regs = reg_repo
        self._waitlist = waitlist_repo
        self._events = event_client
        self._publisher = publisher
        self._context = context_repo

    def execute(
        self,
        *,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int = 1,
        notes: str | None = None,
        email: str = "",
        networking_opt_in: bool = False,
    ) -> RegistrationEntity | WaitlistEntryEntity:
        """
        Check event capacity and either create a confirmed registration or a waitlist entry.

        @param event_id - the event to register for
        @param user_id - UUID from the JWT
        @param quantity - number of tickets, defaults to 1
        @param email - user email from JWT claims, forwarded to domain events for notifications
        @returns RegistrationEntity if a spot is available, WaitlistEntryEntity if full
        @raises EventNotFoundError if the event-service returns 404 or is unreachable
        @raises AlreadyRegisteredError if a non-cancelled registration or waitlist entry exists
        @raises ParticipationConflictError if user is already a volunteer for this event
        """
        event = self._events.get_event(event_id)

        # ! XOR constraint - a user cannot be both attendee and volunteer for the same event
        if self._context is not None and self._context.has_context(event_id, user_id, "volunteer"):
            raise ParticipationConflictError(
                "You are already participating as a volunteer for this event."
            )

        if self._regs.has_active(event_id, user_id):
            raise AlreadyRegisteredError("You are already registered for this event.")

        # ! prevent duplicate waitlist entries  - DB constraint is the final guard
        if self._waitlist.has_entry(event_id, user_id):
            raise AlreadyRegisteredError("You are already on the waitlist for this event.")

        now = datetime.now(timezone.utc)

        if event.is_at_capacity:
            position = self._waitlist.count_for_event(event_id) + 1
            entry = WaitlistEntryEntity(
                id=uuid.uuid4(),
                event_id=event_id,
                user_id=user_id,
                position=position,
                created_at=now,
                expires_at=now + timedelta(hours=_WAITLIST_EXPIRY_HOURS),
            )
            created_entry = self._waitlist.add(entry)
            if self._publisher is not None:
                self._publisher.publish(
                    routing_key="participation.waitlist.joined",
                    payload={
                        "user_id": str(user_id),
                        "event_id": str(event_id),
                        "position": position,
                        "email": email,
                    },
                )
            return created_entry

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
            networking_opt_in=networking_opt_in,
        )
        created = self._regs.create(registration)

        if self._context is not None:
            self._context.set_context(event_id, user_id, "attendee")

        if self._publisher is not None:
            self._publisher.publish(
                routing_key="participation.registration.created",
                payload={
                    "user_id": str(user_id),
                    "event_id": str(event_id),
                    "registration_id": str(created.id),
                    "registration_code": created.registration_code,
                    "email": email,
                    "networking_opt_in": created.networking_opt_in,
                },
            )
        return created
