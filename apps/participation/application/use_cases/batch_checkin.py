"""Use case: batch sync offline check-ins after connectivity is restored."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
from apps.participation.domain.entities import CheckInEntity
from apps.participation.domain.exceptions import (
    InvalidQRTokenError,
    InvalidRegistrationStatusError,
)
from apps.participation.domain.repositories import ICheckInRepository, IRegistrationRepository


class BatchCheckInUseCase:
    """Process a list of offline QR tokens captured when the network was unavailable."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        checkin_repo: ICheckInRepository,
    ) -> None:
        self._regs = reg_repo
        self._checkins = checkin_repo

    def execute(
        self,
        *,
        event_id: uuid.UUID,
        tokens: list[str],
        staff_user_id: uuid.UUID,
    ) -> dict:
        """
        Validate and process each token.

        Returns a summary dict with success/failure counts and per-token results.
        Failed tokens are recorded but do not abort the batch.
        """
        validator = ValidateQRTokenUseCase()
        results = []
        success = 0
        failed = 0

        for token in tokens:
            try:
                payload = validator.execute(token=token, event_id=event_id)
                reg_id = uuid.UUID(payload["registration_id"])
                registration = self._regs.get_by_id(reg_id)

                if registration.status not in ("confirmed", "pending"):
                    raise InvalidRegistrationStatusError(
                        f"Cannot check in: status is '{registration.status}'."
                    )

                if self._checkins.exists_for_registration(reg_id):
                    results.append({"token": token[:8], "status": "already_checked_in"})
                    failed += 1
                    continue

                now = datetime.now(timezone.utc)
                registration.status = "checked_in"
                registration.checked_in_at = now
                registration.updated_at = now
                self._regs.update(registration)

                checkin = CheckInEntity(
                    id=uuid.uuid4(),
                    registration_id=reg_id,
                    event_id=event_id,
                    user_id=registration.user_id,
                    method="offline_qr",
                    checked_in_at=now,
                )
                self._checkins.create(checkin)
                results.append({"token": token[:8], "status": "checked_in"})
                success += 1

            except (InvalidQRTokenError, InvalidRegistrationStatusError, Exception) as exc:
                results.append({"token": token[:8], "status": "failed", "reason": str(exc)})
                failed += 1

        return {"success": success, "failed": failed, "results": results}
