"""Use case: list all registrations belonging to the authenticated user."""

from __future__ import annotations

import uuid

from apps.participation.domain.entities import RegistrationEntity
from apps.participation.domain.repositories import IRegistrationRepository


class ListMyRegistrationsUseCase:
    """Return all registrations owned by a given user."""

    def __init__(self, reg_repo: IRegistrationRepository) -> None:
        self._regs = reg_repo

    def execute(self, *, user_id: uuid.UUID) -> list[RegistrationEntity]:
        """Return all registrations for user_id, newest first."""
        return self._regs.list_by_user(user_id)
