"""Unit tests for Ticket Transfer use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from apps.participation.application.use_cases.accept_transfer import AcceptTransferUseCase
from apps.participation.application.use_cases.cancel_transfer import CancelTransferUseCase
from apps.participation.application.use_cases.initiate_transfer import InitiateTransferUseCase
from apps.participation.domain.exceptions import (
    CannotTransferError,
    RegistrationNotFoundError,
    TransferAlreadyRespondedError,
    TransferExpiredError,
    TransferNotFoundError,
)
from apps.participation.tests.unit.fakes import (
    FakeEventPublisher,
    FakeRegistrationRepository,
    FakeTicketTransferRepository,
    make_registration,
    make_transfer,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestInitiateTransfer:
    """Tests for InitiateTransferUseCase."""

    def test_creates_pending_transfer(self) -> None:
        """Initiating a transfer creates a TicketTransferEntity with pending status."""
        reg = make_registration(status="confirmed")
        reg_repo = FakeRegistrationRepository([reg])
        transfer_repo = FakeTicketTransferRepository()
        publisher = FakeEventPublisher()

        result = InitiateTransferUseCase(
            reg_repo=reg_repo, transfer_repo=transfer_repo, publisher=publisher
        ).execute(
            registration_id=reg.id,
            from_user_id=reg.user_id,
            to_email="recipient@example.com",
        )

        assert result.status == "pending"
        assert result.registration_id == reg.id
        assert result.to_email == "recipient@example.com"
        assert result.expires_at > _now()

    def test_publishes_transfer_event(self) -> None:
        """A participation.transfer.initiated event is published on success."""
        reg = make_registration(status="confirmed")
        publisher = FakeEventPublisher()

        InitiateTransferUseCase(
            reg_repo=FakeRegistrationRepository([reg]),
            transfer_repo=FakeTicketTransferRepository(),
            publisher=publisher,
        ).execute(registration_id=reg.id, from_user_id=reg.user_id, to_email="x@example.com")

        assert len(publisher.events) == 1
        assert publisher.events[0]["routing_key"] == "participation.transfer.initiated"

    def test_raises_if_registration_not_found(self) -> None:
        """Raises RegistrationNotFoundError when the registration does not belong to the user."""
        with pytest.raises(RegistrationNotFoundError):
            InitiateTransferUseCase(
                reg_repo=FakeRegistrationRepository(),
                transfer_repo=FakeTicketTransferRepository(),
            ).execute(
                registration_id=uuid.uuid4(),
                from_user_id=uuid.uuid4(),
                to_email="x@example.com",
            )

    def test_raises_if_registration_not_confirmed(self) -> None:
        """Raises CannotTransferError when registration is not in confirmed status."""
        reg = make_registration(status="cancelled")

        with pytest.raises(CannotTransferError):
            InitiateTransferUseCase(
                reg_repo=FakeRegistrationRepository([reg]),
                transfer_repo=FakeTicketTransferRepository(),
            ).execute(
                registration_id=reg.id,
                from_user_id=reg.user_id,
                to_email="x@example.com",
            )

    def test_raises_if_transfer_already_pending(self) -> None:
        """Raises CannotTransferError when a pending transfer already exists."""
        reg = make_registration(status="confirmed")
        existing = make_transfer(registration_id=reg.id, status="pending")

        with pytest.raises(CannotTransferError):
            InitiateTransferUseCase(
                reg_repo=FakeRegistrationRepository([reg]),
                transfer_repo=FakeTicketTransferRepository([existing]),
            ).execute(
                registration_id=reg.id,
                from_user_id=reg.user_id,
                to_email="x@example.com",
            )


class TestAcceptTransfer:
    """Tests for AcceptTransferUseCase."""

    def test_accept_creates_new_registration(self) -> None:
        """Accepting a transfer creates a new confirmed registration for the recipient."""
        reg = make_registration(status="confirmed")
        transfer = make_transfer(
            registration_id=reg.id,
            status="pending",
            expires_at=_now() + timedelta(hours=48),
        )
        reg_repo = FakeRegistrationRepository([reg])
        transfer_repo = FakeTicketTransferRepository([transfer])
        recipient_id = uuid.uuid4()

        new_reg = AcceptTransferUseCase(reg_repo=reg_repo, transfer_repo=transfer_repo).execute(
            token=transfer.token, recipient_user_id=recipient_id
        )

        assert new_reg.user_id == recipient_id
        assert new_reg.event_id == reg.event_id
        assert new_reg.status == "confirmed"

    def test_accept_cancels_original_registration(self) -> None:
        """Accepting a transfer cancels the original registration."""
        reg = make_registration(status="confirmed")
        transfer = make_transfer(
            registration_id=reg.id,
            status="pending",
            expires_at=_now() + timedelta(hours=48),
        )
        reg_repo = FakeRegistrationRepository([reg])
        transfer_repo = FakeTicketTransferRepository([transfer])

        AcceptTransferUseCase(reg_repo=reg_repo, transfer_repo=transfer_repo).execute(
            token=transfer.token, recipient_user_id=uuid.uuid4()
        )

        assert reg_repo.get_by_id(reg.id).status == "cancelled"

    def test_accept_marks_transfer_completed(self) -> None:
        """Accepting a transfer sets its status to completed."""
        reg = make_registration(status="confirmed")
        transfer = make_transfer(
            registration_id=reg.id,
            status="pending",
            expires_at=_now() + timedelta(hours=48),
        )
        reg_repo = FakeRegistrationRepository([reg])
        transfer_repo = FakeTicketTransferRepository([transfer])

        AcceptTransferUseCase(reg_repo=reg_repo, transfer_repo=transfer_repo).execute(
            token=transfer.token, recipient_user_id=uuid.uuid4()
        )

        updated = transfer_repo.get_by_token(transfer.token)
        assert updated is not None
        assert updated.status == "completed"

    def test_accept_raises_if_token_not_found(self) -> None:
        """Raises TransferNotFoundError for an unknown token."""
        with pytest.raises(TransferNotFoundError):
            AcceptTransferUseCase(
                reg_repo=FakeRegistrationRepository(),
                transfer_repo=FakeTicketTransferRepository(),
            ).execute(token=uuid.uuid4(), recipient_user_id=uuid.uuid4())

    def test_accept_raises_if_expired(self) -> None:
        """Raises TransferExpiredError when the 48-hour acceptance window has passed."""
        reg = make_registration(status="confirmed")
        transfer = make_transfer(
            registration_id=reg.id,
            status="pending",
            expires_at=_now() - timedelta(hours=1),
        )

        with pytest.raises(TransferExpiredError):
            AcceptTransferUseCase(
                reg_repo=FakeRegistrationRepository([reg]),
                transfer_repo=FakeTicketTransferRepository([transfer]),
            ).execute(token=transfer.token, recipient_user_id=uuid.uuid4())

    def test_accept_raises_if_already_responded(self) -> None:
        """Raises TransferAlreadyRespondedError for non-pending transfers."""
        reg = make_registration(status="cancelled")
        transfer = make_transfer(
            registration_id=reg.id,
            status="completed",
            expires_at=_now() + timedelta(hours=48),
        )

        with pytest.raises(TransferAlreadyRespondedError):
            AcceptTransferUseCase(
                reg_repo=FakeRegistrationRepository([reg]),
                transfer_repo=FakeTicketTransferRepository([transfer]),
            ).execute(token=transfer.token, recipient_user_id=uuid.uuid4())


class TestCancelTransfer:
    """Tests for CancelTransferUseCase."""

    def test_cancel_sets_status_cancelled(self) -> None:
        """Cancelling a pending transfer sets its status to cancelled."""
        transfer = make_transfer(status="pending")
        transfer_repo = FakeTicketTransferRepository([transfer])

        CancelTransferUseCase(transfer_repo=transfer_repo).execute(
            transfer_id=transfer.id,
            user_id=transfer.from_user_id,
        )

        updated = transfer_repo.get_by_id(transfer.id)
        assert updated is not None
        assert updated.status == "cancelled"

    def test_cancel_raises_if_not_found(self) -> None:
        """Raises TransferNotFoundError for an unknown transfer_id."""
        with pytest.raises(TransferNotFoundError):
            CancelTransferUseCase(transfer_repo=FakeTicketTransferRepository()).execute(
                transfer_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )

    def test_cancel_raises_if_not_owner(self) -> None:
        """Raises TransferNotFoundError when user is not the transfer initiator."""
        transfer = make_transfer(status="pending")
        transfer_repo = FakeTicketTransferRepository([transfer])

        with pytest.raises(TransferNotFoundError):
            CancelTransferUseCase(transfer_repo=transfer_repo).execute(
                transfer_id=transfer.id,
                user_id=uuid.uuid4(),  # different user
            )

    def test_cancel_raises_if_already_responded(self) -> None:
        """Raises TransferAlreadyRespondedError for non-pending transfers."""
        transfer = make_transfer(status="completed")
        transfer_repo = FakeTicketTransferRepository([transfer])

        with pytest.raises(TransferAlreadyRespondedError):
            CancelTransferUseCase(transfer_repo=transfer_repo).execute(
                transfer_id=transfer.id,
                user_id=transfer.from_user_id,
            )
