"""Use case: cancel a pending ticket transfer."""

from __future__ import annotations

import uuid

from apps.participation.domain.exceptions import (
    TransferAlreadyRespondedError,
    TransferNotFoundError,
)
from apps.participation.domain.repositories import ITicketTransferRepository


class CancelTransferUseCase:
    """Cancel a pending transfer initiated by the requesting user."""

    def __init__(self, *, transfer_repo: ITicketTransferRepository) -> None:
        self._transfers = transfer_repo

    def execute(self, *, transfer_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Validate ownership and pending status, then mark the transfer cancelled.

        Raises TransferNotFoundError if the transfer is unknown or belongs to another user.
        Raises TransferAlreadyRespondedError if the transfer is no longer pending.
        """
        transfer = self._transfers.get_by_id(transfer_id)
        if transfer is None or transfer.from_user_id != user_id:
            raise TransferNotFoundError("Transfer not found.")

        if transfer.status != "pending":
            raise TransferAlreadyRespondedError("Transfer has already been responded to.")

        transfer.status = "cancelled"
        self._transfers.update(transfer)
