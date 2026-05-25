"""Use case: initiate a ticket transfer from one user to another."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from apps.participation.domain.entities import TicketTransferEntity
from apps.participation.domain.exceptions import CannotTransferError
from apps.participation.domain.repositories import (
    IEventPublisher,
    IRegistrationRepository,
    ITicketTransferRepository,
)

# ! transfer offers expire after 48 hours - recipient must accept within this window
_TRANSFER_EXPIRY_HOURS = 48


class InitiateTransferUseCase:
    """Start a ticket transfer by creating a pending TicketTransferEntity."""

    def __init__(
        self,
        *,
        reg_repo: IRegistrationRepository,
        transfer_repo: ITicketTransferRepository,
        publisher: IEventPublisher | None = None,
    ) -> None:
        self._regs = reg_repo
        self._transfers = transfer_repo
        self._publisher = publisher

    def execute(
        self,
        *,
        registration_id: uuid.UUID,
        from_user_id: uuid.UUID,
        to_email: str,
    ) -> TicketTransferEntity:
        """
        Validate ownership and status, then create a pending transfer token.

        Raises RegistrationNotFoundError if the registration does not belong to from_user_id.
        Raises CannotTransferError if the registration is not confirmed or has a pending transfer.
        """
        registration = self._regs.get_by_id_for_user(registration_id, from_user_id)

        if registration.status != "confirmed":
            raise CannotTransferError("Only confirmed registrations can be transferred.")

        if self._transfers.get_pending_for_registration(registration_id) is not None:
            raise CannotTransferError("A pending transfer already exists for this registration.")

        now = datetime.now(timezone.utc)
        transfer = TicketTransferEntity(
            id=uuid.uuid4(),
            registration_id=registration_id,
            from_user_id=from_user_id,
            to_email=to_email,
            token=uuid.uuid4(),
            status="pending",
            created_at=now,
            expires_at=now + timedelta(hours=_TRANSFER_EXPIRY_HOURS),
        )
        self._transfers.create(transfer)

        if self._publisher is not None:
            self._publisher.publish(
                routing_key="participation.transfer.initiated",
                payload={
                    "transfer_id": str(transfer.id),
                    "registration_id": str(registration_id),
                    "from_user_id": str(from_user_id),
                    "to_email": to_email,
                    "token": str(transfer.token),
                    "expires_at": transfer.expires_at.isoformat(),
                },
            )

        return transfer
