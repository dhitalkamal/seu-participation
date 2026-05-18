"""Unit tests for the Verified Event Passport."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.participation.tests.unit.fakes import FakeRegistrationRepository, make_registration


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_passport_includes_confirmed_registrations():
    """GetPassportUseCase includes registrations with status confirmed or checked_in."""
    from apps.participation.application.use_cases.get_passport import GetPassportUseCase

    user_id = uuid.uuid4()
    confirmed = make_registration(status="confirmed", user_id=user_id)
    checked_in = make_registration(status="checked_in", user_id=user_id)
    cancelled = make_registration(status="cancelled", user_id=user_id)

    repo = FakeRegistrationRepository([confirmed, checked_in, cancelled])
    passport = GetPassportUseCase(repo).execute(user_id=user_id)

    assert len(passport.entries) == 2
    assert passport.user_id == user_id


def test_passport_has_valid_hmac_signature():
    """Passport signature can be verified with the platform key."""
    from apps.participation.application.use_cases.get_passport import GetPassportUseCase
    from apps.participation.application.use_cases.verify_passport import VerifyPassportUseCase

    user_id = uuid.uuid4()
    reg = make_registration(status="checked_in", user_id=user_id)
    repo = FakeRegistrationRepository([reg])
    passport = GetPassportUseCase(repo).execute(user_id=user_id)

    assert VerifyPassportUseCase().execute(passport=passport) is True


def test_passport_tampered_signature_fails():
    """Modified passport fails signature verification."""
    from apps.participation.application.use_cases.get_passport import GetPassportUseCase
    from apps.participation.application.use_cases.verify_passport import VerifyPassportUseCase

    user_id = uuid.uuid4()
    reg = make_registration(status="checked_in", user_id=user_id)
    repo = FakeRegistrationRepository([reg])
    passport = GetPassportUseCase(repo).execute(user_id=user_id)

    passport.signature = "tampered_signature"
    assert VerifyPassportUseCase().execute(passport=passport) is False


def test_passport_empty_for_user_with_no_registrations():
    """Passport has empty entries for a user with no completed registrations."""
    from apps.participation.application.use_cases.get_passport import GetPassportUseCase

    repo = FakeRegistrationRepository()
    passport = GetPassportUseCase(repo).execute(user_id=uuid.uuid4())
    assert passport.entries == []
