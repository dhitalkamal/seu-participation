"""Use case: get check-in stats for an event (used by the volunteer dashboard)."""

from __future__ import annotations

import uuid
from typing import Protocol


class IRegistrationStatsRepository(Protocol):
    """Read-only interface for registration counts."""

    def count_for_event(self, event_id: uuid.UUID) -> int: ...
    def count_checked_in_for_event(self, event_id: uuid.UUID) -> int: ...


class GetEventCheckInStatsUseCase:
    """Return total, checked-in, and remaining counts for a volunteer's dashboard."""

    def __init__(self, repo: IRegistrationStatsRepository) -> None:
        self._repo = repo

    def execute(self, *, event_id: uuid.UUID) -> dict[str, int]:
        """
        Compute real-time check-in progress for an event.

        @param event_id - the target event's UUID
        @returns dict with total, checked_in, and remaining keys
        """
        total = self._repo.count_for_event(event_id)
        checked_in = self._repo.count_checked_in_for_event(event_id)
        return {
            "total": total,
            "checked_in": checked_in,
            "remaining": total - checked_in,
        }
