"""Integration tests for ticket transfer HTTP endpoints."""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from apps.participation.infrastructure.models import Registration, TicketTransfer


class _FakeUser:
    """Minimal user object for force_authenticate."""

    def __init__(self, user_id: uuid.UUID) -> None:
        self.id = user_id
        self.is_authenticated = True
        self.is_active = True
        self.token: dict = {}


@pytest.fixture()
def api_client() -> APIClient:
    """Return a fresh DRF test client."""
    return APIClient()


@pytest.fixture()
def user_id() -> uuid.UUID:
    """A stable UUID representing the authenticated user."""
    return uuid.uuid4()


@pytest.fixture()
def confirmed_registration(user_id: uuid.UUID) -> Registration:
    """A confirmed Registration owned by user_id, saved to the test DB."""
    return Registration.objects.create(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        user_id=user_id,
        status="confirmed",
        registration_code="TST12345",
        quantity=1,
    )


# * initiate transfer


@pytest.mark.django_db
class TestInitiateTransferView:
    """POST /api/v1/registrations/<id>/transfer/"""

    def test_returns_201_with_pending_transfer(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
        confirmed_registration: Registration,
    ) -> None:
        """Happy path: a confirmed registration produces a pending transfer."""
        api_client.force_authenticate(user=_FakeUser(user_id))
        resp = api_client.post(
            f"/api/v1/registrations/{confirmed_registration.id}/transfer/",
            {"to_email": "recipient@example.com"},
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["status"] == "pending"
        assert data["to_email"] == "recipient@example.com"
        assert data["registration_id"] == str(confirmed_registration.id)

    def test_returns_404_for_unknown_registration(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
    ) -> None:
        """Returns 404 when the registration does not exist or belong to the user."""
        api_client.force_authenticate(user=_FakeUser(user_id))
        resp = api_client.post(
            f"/api/v1/registrations/{uuid.uuid4()}/transfer/",
            {"to_email": "x@example.com"},
            format="json",
        )
        assert resp.status_code == 404

    def test_returns_409_when_transfer_already_pending(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
        confirmed_registration: Registration,
    ) -> None:
        """Returns 409 when a pending transfer already exists for the registration."""
        api_client.force_authenticate(user=_FakeUser(user_id))
        # first transfer
        api_client.post(
            f"/api/v1/registrations/{confirmed_registration.id}/transfer/",
            {"to_email": "first@example.com"},
            format="json",
        )
        # second attempt should conflict
        resp = api_client.post(
            f"/api/v1/registrations/{confirmed_registration.id}/transfer/",
            {"to_email": "second@example.com"},
            format="json",
        )
        assert resp.status_code == 409

    def test_returns_401_without_auth(
        self,
        api_client: APIClient,
        confirmed_registration: Registration,
    ) -> None:
        """Returns 401 when no authentication is provided."""
        resp = api_client.post(
            f"/api/v1/registrations/{confirmed_registration.id}/transfer/",
            {"to_email": "x@example.com"},
            format="json",
        )
        assert resp.status_code == 401


# * accept transfer


@pytest.mark.django_db
class TestAcceptTransferView:
    """POST /api/v1/transfers/<token>/accept/"""

    def _create_pending_transfer(self, registration: Registration) -> TicketTransfer:
        """Insert a pending TicketTransfer directly into the test DB."""
        from datetime import timedelta

        from django.utils import timezone

        return TicketTransfer.objects.create(
            id=uuid.uuid4(),
            registration=registration,
            from_user_id=registration.user_id,
            to_email="recipient@example.com",
            token=uuid.uuid4(),
            status="pending",
            expires_at=timezone.now() + timedelta(hours=48),
        )

    def test_returns_201_and_creates_new_registration(
        self,
        api_client: APIClient,
        confirmed_registration: Registration,
    ) -> None:
        """Accepting a valid transfer creates a new confirmed registration."""
        transfer = self._create_pending_transfer(confirmed_registration)
        recipient_id = uuid.uuid4()
        api_client.force_authenticate(user=_FakeUser(recipient_id))

        resp = api_client.post(
            f"/api/v1/transfers/{transfer.token}/accept/",
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["status"] == "confirmed"
        assert data["user_id"] == str(recipient_id)
        assert data["event_id"] == str(confirmed_registration.event_id)

    def test_returns_404_for_unknown_token(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
    ) -> None:
        """Returns 404 for a token that does not exist."""
        api_client.force_authenticate(user=_FakeUser(user_id))
        resp = api_client.post(f"/api/v1/transfers/{uuid.uuid4()}/accept/", format="json")
        assert resp.status_code == 404

    def test_returns_409_when_already_responded(
        self,
        api_client: APIClient,
        confirmed_registration: Registration,
    ) -> None:
        """Returns 409 when the transfer is not in pending status."""
        from datetime import timedelta

        from django.utils import timezone

        transfer = TicketTransfer.objects.create(
            id=uuid.uuid4(),
            registration=confirmed_registration,
            from_user_id=confirmed_registration.user_id,
            to_email="x@example.com",
            token=uuid.uuid4(),
            status="completed",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        api_client.force_authenticate(user=_FakeUser(uuid.uuid4()))
        resp = api_client.post(f"/api/v1/transfers/{transfer.token}/accept/", format="json")
        assert resp.status_code == 409


# * cancel transfer


@pytest.mark.django_db
class TestCancelTransferView:
    """DELETE /api/v1/transfers/<id>/"""

    def _create_pending_transfer(
        self, registration: Registration, owner_id: uuid.UUID
    ) -> TicketTransfer:
        """Insert a pending TicketTransfer owned by owner_id."""
        from datetime import timedelta

        from django.utils import timezone

        return TicketTransfer.objects.create(
            id=uuid.uuid4(),
            registration=registration,
            from_user_id=owner_id,
            to_email="r@example.com",
            token=uuid.uuid4(),
            status="pending",
            expires_at=timezone.now() + timedelta(hours=48),
        )

    def test_returns_200_and_cancels_transfer(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
        confirmed_registration: Registration,
    ) -> None:
        """Owner cancelling a pending transfer receives 200."""
        transfer = self._create_pending_transfer(confirmed_registration, user_id)
        api_client.force_authenticate(user=_FakeUser(user_id))
        resp = api_client.delete(f"/api/v1/transfers/{transfer.id}/")
        assert resp.status_code == 200

    def test_returns_404_for_different_user(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
        confirmed_registration: Registration,
    ) -> None:
        """Non-owner cannot cancel another user's transfer."""
        transfer = self._create_pending_transfer(confirmed_registration, user_id)
        api_client.force_authenticate(user=_FakeUser(uuid.uuid4()))
        resp = api_client.delete(f"/api/v1/transfers/{transfer.id}/")
        assert resp.status_code == 404

    def test_returns_409_when_already_responded(
        self,
        api_client: APIClient,
        user_id: uuid.UUID,
        confirmed_registration: Registration,
    ) -> None:
        """Returns 409 when the transfer is already completed."""
        from datetime import timedelta

        from django.utils import timezone

        transfer = TicketTransfer.objects.create(
            id=uuid.uuid4(),
            registration=confirmed_registration,
            from_user_id=user_id,
            to_email="r@example.com",
            token=uuid.uuid4(),
            status="completed",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        api_client.force_authenticate(user=_FakeUser(user_id))
        resp = api_client.delete(f"/api/v1/transfers/{transfer.id}/")
        assert resp.status_code == 409
