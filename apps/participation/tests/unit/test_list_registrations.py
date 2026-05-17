"""Unit tests for ListMyRegistrationsUseCase and GetRegistrationUseCase."""

from __future__ import annotations

import uuid

import pytest

from apps.participation.application.use_cases.get_registration import GetRegistrationUseCase
from apps.participation.application.use_cases.list_my_registrations import (
    ListMyRegistrationsUseCase,
)
from apps.participation.domain.exceptions import RegistrationNotFoundError
from apps.participation.tests.unit.fakes import FakeRegistrationRepository, make_registration


def test_list_returns_own_registrations():
    """Returns only registrations owned by the user."""
    user_id = uuid.uuid4()
    own = [make_registration(user_id=user_id) for _ in range(3)]
    other = make_registration()
    repo = FakeRegistrationRepository(own + [other])
    results = ListMyRegistrationsUseCase(repo).execute(user_id=user_id)
    assert len(results) == 3
    assert all(r.user_id == user_id for r in results)


def test_list_returns_empty_when_none():
    """Returns empty list when the user has no registrations."""
    repo = FakeRegistrationRepository()
    assert ListMyRegistrationsUseCase(repo).execute(user_id=uuid.uuid4()) == []


def test_get_returns_own_registration():
    """Returns the registration when it belongs to the user."""
    reg = make_registration()
    repo = FakeRegistrationRepository([reg])
    result = GetRegistrationUseCase(repo).execute(
        registration_id=reg.id, user_id=reg.user_id
    )
    assert result.id == reg.id


def test_get_wrong_user_raises():
    """Raises RegistrationNotFoundError when the user does not own the registration."""
    reg = make_registration()
    repo = FakeRegistrationRepository([reg])
    with pytest.raises(RegistrationNotFoundError):
        GetRegistrationUseCase(repo).execute(
            registration_id=reg.id, user_id=uuid.uuid4()
        )


def test_get_missing_raises():
    """Raises RegistrationNotFoundError when the registration does not exist."""
    repo = FakeRegistrationRepository()
    with pytest.raises(RegistrationNotFoundError):
        GetRegistrationUseCase(repo).execute(
            registration_id=uuid.uuid4(), user_id=uuid.uuid4()
        )
