"""Use case: register a user for an event or add them to the waitlist."""

from __future__ import annotations

import logging
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.participation.domain.entities import RegistrationEntity, WaitlistEntryEntity
from apps.participation.domain.exceptions import AlreadyRegisteredError, ParticipationConflictError
from apps.participation.domain.repositories import (
    IEventClient,
    IEventPublisher,
    IParticipationContextRepository,
    IRegistrationRepository,
    IWaitlistRepository,
)

logger = logging.getLogger(__name__)

# ! waitlist slots expire after 24 hours  - promoted user must act within this window
_WAITLIST_EXPIRY_HOURS = 24


def _generate_code() -> str:
    """Generate a unique 8-character alphanumeric registration code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _redis_key(event_id: uuid.UUID) -> str:
    """Return the Redis capacity key for the given event."""
    return f"event_capacity:{event_id}"


def _is_at_capacity_redis(event_id: uuid.UUID, event_capacity: int, redis_client: Any) -> bool:
    """
    Check Redis for the current registered count. Falls back to True when Redis fails.

    Uses Redis as the fast path; on any error returns None to signal fallback.

    @param event_id - the event to check
    @param event_capacity - the authoritative capacity from event-service
    @param redis_client - a Redis connection or compatible client
    @returns True if at capacity, False if not, or re-raises to trigger fallback
    """
    try:
        raw = redis_client.get(_redis_key(event_id))
        if raw is None:
            return False  # no counter seeded yet, treat as not full
        return int(raw) >= event_capacity
    except Exception:
        logger.warning(
            "Redis unavailable for capacity check on event %s, falling back to DB", event_id
        )
        raise  # caller catches and falls back to event summary


class RegisterForEventUseCase:
    """Register a user for an event or add them to the waitlist if full."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        waitlist_repo: IWaitlistRepository,
        event_client: IEventClient,
        publisher: IEventPublisher | None = None,
        context_repo: IParticipationContextRepository | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._regs = reg_repo
        self._waitlist = waitlist_repo
        self._events = event_client
        self._publisher = publisher
        self._context = context_repo
        self._redis = redis_client

    def execute(
        self,
        *,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int = 1,
        notes: str | None = None,
        email: str = "",
        first_name: str = "",
        networking_opt_in: bool = False,
    ) -> RegistrationEntity | WaitlistEntryEntity:
        """
        Check event capacity and either create a confirmed registration or a waitlist entry.

        When a Redis client is provided, capacity is read from Redis first for speed.
        Falls back to the event-service response if Redis is unavailable.

        @param event_id    - the event to register for
        @param user_id     - UUID from the JWT
        @param quantity    - number of tickets, defaults to 1
        @param email       - user email from JWT claims, forwarded to domain events
        @param first_name  - user's first name from JWT claims, used for email personalisation
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

        # fast-path capacity check via Redis; fall back to event summary on failure
        if self._redis is not None:
            try:
                at_capacity = _is_at_capacity_redis(event_id, event.capacity, self._redis)
            except Exception:
                at_capacity = event.is_at_capacity
        else:
            at_capacity = event.is_at_capacity

        if at_capacity:
            position = self._waitlist.count_for_event(event_id) + 1
            entry = WaitlistEntryEntity(
                id=uuid.uuid4(),
                event_id=event_id,
                user_id=user_id,
                position=position,
                created_at=now,
                expires_at=now + timedelta(hours=_WAITLIST_EXPIRY_HOURS),
                email=email,
                first_name=first_name,
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
                        "first_name": first_name,
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
                    "first_name": first_name,
                    "networking_opt_in": created.networking_opt_in,
                },
            )

        # atomically increment Redis counter; failure is non-fatal
        if self._redis is not None:
            try:
                self._redis.incr(_redis_key(event_id))
            except Exception:
                logger.warning("Redis INCR failed for event_capacity:%s", event_id)

        return created
