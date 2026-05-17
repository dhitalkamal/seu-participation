"""Use case: check in a registration by registration_code."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.domain.entities import CheckInEntity
from apps.participation.domain.exceptions import InvalidRegistrationStatusError
from apps.participation.domain.repositories import ICheckInRepository, IRegistrationRepository


class CheckInUseCase:
    """Check in a confirmed registration and create a CheckIn record."""

    def __init__(
        self,
        reg_repo: IRegistrationRepository,
        check_in_repo: ICheckInRepository,
    ) -> None:
        self._regs = reg_repo
        self._check_ins = check_in_repo

    def execute(
        self,
        *,
        registration_code: str,
        method: str,
        staff_user_id: uuid.UUID,
    ) -> CheckInEntity:
        """
        Validate the registration code, check status, and record the check-in.

        @param registration_code - the 8-char code from the QR or manual entry
        @param method - qr_code | manual
        @param staff_user_id - UUID of the staff member performing the check-in
        @returns the created CheckInEntity
        @raises RegistrationNotFoundError if the code is not found
        @raises InvalidRegistrationStatusError if not CONFIRMED or already checked in
        """
        registration = self._regs.get_by_code(registration_code)

        if registration.status != "confirmed":
            raise InvalidRegistrationStatusError(
                f"Cannot check in a registration with status '{registration.status}'."
            )

        if self._check_ins.exists_for_registration(registration.id):
            raise InvalidRegistrationStatusError("This registration has already been checked in.")

        now = datetime.now(timezone.utc)
        registration.status = "checked_in"
        registration.checked_in_at = now
        registration.updated_at = now
        self._regs.update(registration)

        check_in = CheckInEntity(
            id=uuid.uuid4(),
            registration_id=registration.id,
            event_id=registration.event_id,
            user_id=registration.user_id,
            method=method,
            checked_in_at=now,
        )
        return self._check_ins.create(check_in)
