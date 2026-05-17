"""Unit tests for CheckInUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.participation.application.use_cases.check_in import CheckInUseCase
from apps.participation.domain.entities import CheckInEntity
from apps.participation.domain.exceptions import InvalidRegistrationStatusError
from apps.participation.tests.unit.fakes import (
    FakeCheckInRepository,
    FakeRegistrationRepository,
    make_registration,
)


def _uc(regs=None, check_ins=None) -> CheckInUseCase:
    return CheckInUseCase(
        reg_repo=FakeRegistrationRepository(regs or []),
        check_in_repo=FakeCheckInRepository(check_ins or []),
    )


def test_check_in_creates_check_in_record():
    """Successful check-in returns a CheckInEntity with correct fields."""
    reg = make_registration(status="confirmed")
    result = _uc(regs=[reg]).execute(
        registration_code=reg.registration_code,
        method="qr_code",
        staff_user_id=uuid.uuid4(),
    )
    assert isinstance(result, CheckInEntity)
    assert result.registration_id == reg.id
    assert result.event_id == reg.event_id
    assert result.method == "qr_code"


def test_check_in_sets_registration_to_checked_in():
    """After check-in the registration has status=checked_in and checked_in_at set."""
    reg = make_registration(status="confirmed")
    reg_repo = FakeRegistrationRepository([reg])
    CheckInUseCase(reg_repo=reg_repo, check_in_repo=FakeCheckInRepository()).execute(
        registration_code=reg.registration_code,
        method="manual",
        staff_user_id=uuid.uuid4(),
    )
    updated = reg_repo.get_by_id(reg.id)
    assert updated.status == "checked_in"
    assert updated.checked_in_at is not None


def test_check_in_non_confirmed_raises():
    """Checking in a cancelled registration raises InvalidRegistrationStatusError."""
    reg = make_registration(status="cancelled")
    with pytest.raises(InvalidRegistrationStatusError):
        _uc(regs=[reg]).execute(
            registration_code=reg.registration_code,
            method="qr_code",
            staff_user_id=uuid.uuid4(),
        )


def test_check_in_already_checked_in_raises():
    """Double check-in raises InvalidRegistrationStatusError."""
    reg = make_registration(status="confirmed")
    existing = CheckInEntity(
        id=uuid.uuid4(),
        registration_id=reg.id,
        event_id=reg.event_id,
        user_id=reg.user_id,
        method="qr_code",
        checked_in_at=datetime.now(timezone.utc),
    )
    with pytest.raises(InvalidRegistrationStatusError):
        _uc(regs=[reg], check_ins=[existing]).execute(
            registration_code=reg.registration_code,
            method="manual",
            staff_user_id=uuid.uuid4(),
        )
