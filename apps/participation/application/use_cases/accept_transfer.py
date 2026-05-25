"""Use case: accept a pending ticket transfer and create a new registration."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone

from apps.participation.domain.entities import RegistrationEntity
from apps.participation.domain.exceptions import (
    TransferAlreadyRespondedError,
    TransferExpiredError,
    TransferNotFoundError,
)
from apps.participation.domain.repositories import (
    IRegistrationRepository,
    ITicketTransferRepository,
)


def _generate_code() -> str:
    """Generate a unique 8-character alphanumeric registration code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class AcceptTransferUseCase:
    """Accept a pending transfer, cancel the original registration, and create a new one."""

    def __init__(
        self,
        *,
        reg_repo: IRegistrationRepository,
        transfer_repo: ITicketTransferRepository,
    ) -> None:
        self._regs = reg_repo
        self._transfers = transfer_repo

    def execute(
        self,
        *,
        token: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> RegistrationEntity:
        """
        Look up the transfer by token, validate it, then swap ownership.

        Raises TransferNotFoundError if the token is unknown.
        Raises TransferExpiredError if the 48-hour window has passed.
        Raises TransferAlreadyRespondedError if the transfer is not pending.
        """
        transfer = self._transfers.get_by_token(token)
        if transfer is None:
            raise TransferNotFoundError("Transfer not found.")

        now = datetime.now(timezone.utc)
        if transfer.expires_at <= now:
            raise TransferExpiredError("Transfer offer has expired.")

        if transfer.status != "pending":
            raise TransferAlreadyRespondedError("Transfer has already been responded to.")

        original = self._regs.get_by_id(transfer.registration_id)

        new_reg = RegistrationEntity(
            id=uuid.uuid4(),
            event_id=original.event_id,
            user_id=recipient_user_id,
            status="confirmed",
            registration_code=_generate_code(),
            quantity=original.quantity,
            created_at=now,
            updated_at=now,
        )
        self._regs.create(new_reg)

        original.status = "cancelled"
        original.cancelled_at = now
        original.updated_at = now
        self._regs.update(original)

        transfer.status = "completed"
        self._transfers.update(transfer)

        return new_reg
