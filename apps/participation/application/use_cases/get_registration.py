"""Use case: retrieve a single registration owned by the requesting user."""

from __future__ import annotations

import uuid

from apps.participation.domain.entities import RegistrationEntity
from apps.participation.domain.repositories import IRegistrationRepository


class GetRegistrationUseCase:
    """Fetch a registration, enforcing ownership."""

    def __init__(self, reg_repo: IRegistrationRepository) -> None:
        self._regs = reg_repo

    def execute(
        self, *, registration_id: uuid.UUID, user_id: uuid.UUID
    ) -> RegistrationEntity:
        """
        Return the registration if it exists and belongs to user_id.

        @param registration_id - UUID of the registration to fetch
        @param user_id - UUID from JWT; must match registration.user_id
        @raises RegistrationNotFoundError if absent or not owned by the user
        """
        return self._regs.get_by_id_for_user(registration_id, user_id)
