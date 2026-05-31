"""Use case: list all volunteer shifts assigned to the requesting user."""

from __future__ import annotations

import uuid
from typing import Protocol

from apps.participation.domain.entities import VolunteerShiftEntity


class IShiftRepository(Protocol):
    """Read interface for volunteer shift storage."""

    def list_for_user(self, user_id: uuid.UUID) -> list[VolunteerShiftEntity]: ...


class ListMyShiftsUseCase:
    """Return all shifts assigned to a specific volunteer."""

    def __init__(self, repo: IShiftRepository) -> None:
        self._repo = repo

    def execute(self, *, user_id: uuid.UUID) -> list[VolunteerShiftEntity]:
        """
        Fetch every shift assigned to this user, ordered by start time.

        @param user_id - the authenticated volunteer's ID
        @returns list of VolunteerShiftEntity sorted by start_time ascending
        """
        shifts = self._repo.list_for_user(user_id)
        return sorted(shifts, key=lambda s: s.start_time)
