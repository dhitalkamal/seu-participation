"""Unit tests for Redis capacity integration in register and cancel use cases."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from apps.participation.application.use_cases.cancel import CancelRegistrationUseCase
from apps.participation.application.use_cases.register import RegisterForEventUseCase
from apps.participation.tests.unit.fakes import (
    FakeEventClient,
    FakeRegistrationRepository,
    FakeWaitlistRepository,
    make_event_summary,
    make_registration,
)


class TestRegisterIncreasesRedisCounter:
    """RegisterForEventUseCase increments Redis capacity on successful registration."""

    def test_incr_called_after_registration(self) -> None:
        """INCR must be called on event_capacity:{event_id} after a confirmed registration."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = make_event_summary(event_id=event_id, capacity=100, registered_count=0)

        reg_repo = FakeRegistrationRepository()
        waitlist_repo = FakeWaitlistRepository()
        event_client = FakeEventClient(event=event)
        mock_redis = MagicMock()

        RegisterForEventUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            event_client=event_client,
            redis_client=mock_redis,
        ).execute(event_id=event_id, user_id=user_id)

        mock_redis.incr.assert_called_once_with(f"event_capacity:{event_id}")

    def test_incr_not_called_when_waitlisted(self) -> None:
        """INCR must NOT be called when the user ends up on the waitlist (event is full)."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # full event - both event-service and Redis agree it's full
        event = make_event_summary(event_id=event_id, capacity=10, registered_count=10)

        reg_repo = FakeRegistrationRepository()
        waitlist_repo = FakeWaitlistRepository()
        event_client = FakeEventClient(event=event)
        mock_redis = MagicMock()
        # Redis also shows full (10/10)
        mock_redis.get.return_value = b"10"

        RegisterForEventUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            event_client=event_client,
            redis_client=mock_redis,
        ).execute(event_id=event_id, user_id=user_id)

        mock_redis.incr.assert_not_called()

    def test_redis_unavailable_does_not_break_registration(self) -> None:
        """A Redis INCR failure must not prevent the registration from completing."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = make_event_summary(event_id=event_id, capacity=100, registered_count=0)

        reg_repo = FakeRegistrationRepository()
        waitlist_repo = FakeWaitlistRepository()
        event_client = FakeEventClient(event=event)
        mock_redis = MagicMock()
        mock_redis.incr.side_effect = Exception("connection refused")

        # should not raise
        result = RegisterForEventUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            event_client=event_client,
            redis_client=mock_redis,
        ).execute(event_id=event_id, user_id=user_id)

        from apps.participation.domain.entities import RegistrationEntity

        assert isinstance(result, RegistrationEntity)
        assert result.status == "confirmed"


class TestRegisterChecksRedisCapacity:
    """RegisterForEventUseCase checks Redis counter before allowing registration."""

    def test_registration_blocked_when_redis_count_at_capacity(self) -> None:
        """If Redis says the event is full, block even if event-service returns not full."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # event-service says 5/100 (not full)
        event = make_event_summary(event_id=event_id, capacity=100, registered_count=5)

        reg_repo = FakeRegistrationRepository()
        waitlist_repo = FakeWaitlistRepository()
        event_client = FakeEventClient(event=event)
        mock_redis = MagicMock()
        # Redis says 100 - full
        mock_redis.get.return_value = b"100"

        from apps.participation.domain.entities import WaitlistEntryEntity

        result = RegisterForEventUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            event_client=event_client,
            redis_client=mock_redis,
        ).execute(event_id=event_id, user_id=user_id)

        # should be waitlisted because Redis says full
        assert isinstance(result, WaitlistEntryEntity)

    def test_falls_back_to_event_service_when_redis_unavailable(self) -> None:
        """When Redis raises, capacity check falls back to event-service data."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # event-service says not full
        event = make_event_summary(event_id=event_id, capacity=100, registered_count=5)

        reg_repo = FakeRegistrationRepository()
        waitlist_repo = FakeWaitlistRepository()
        event_client = FakeEventClient(event=event)
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("redis down")

        from apps.participation.domain.entities import RegistrationEntity

        result = RegisterForEventUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            event_client=event_client,
            redis_client=mock_redis,
        ).execute(event_id=event_id, user_id=user_id)

        assert isinstance(result, RegistrationEntity)
        assert result.status == "confirmed"


class TestCancelDecreasesRedisCounter:
    """CancelRegistrationUseCase decrements Redis capacity on cancellation."""

    def test_decr_called_after_cancellation(self) -> None:
        """DECR must be called on event_capacity:{event_id} after a successful cancellation."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        registration = make_registration(event_id=event_id, user_id=user_id, status="confirmed")

        reg_repo = FakeRegistrationRepository(registrations=[registration])
        waitlist_repo = FakeWaitlistRepository()
        mock_redis = MagicMock()

        CancelRegistrationUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            redis_client=mock_redis,
        ).execute(registration_id=registration.id, user_id=user_id)

        mock_redis.decr.assert_called_once_with(f"event_capacity:{event_id}")

    def test_redis_unavailable_does_not_break_cancellation(self) -> None:
        """A Redis DECR failure must not prevent the cancellation from completing."""
        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        registration = make_registration(event_id=event_id, user_id=user_id, status="confirmed")

        reg_repo = FakeRegistrationRepository(registrations=[registration])
        waitlist_repo = FakeWaitlistRepository()
        mock_redis = MagicMock()
        mock_redis.decr.side_effect = Exception("connection refused")

        result = CancelRegistrationUseCase(
            reg_repo=reg_repo,
            waitlist_repo=waitlist_repo,
            redis_client=mock_redis,
        ).execute(registration_id=registration.id, user_id=user_id)

        assert result.status == "cancelled"
