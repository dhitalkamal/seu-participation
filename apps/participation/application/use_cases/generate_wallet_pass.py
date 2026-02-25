"""Use case: generate an Apple or Google Wallet pass for a confirmed registration."""

from __future__ import annotations

import uuid

from apps.participation.domain.entities import WalletPassEntity
from apps.participation.domain.exceptions import InvalidRegistrationStatusError
from apps.participation.domain.repositories import IRegistrationRepository, IWalletPassGenerator


class GenerateWalletPassUseCase:
    """Build a wallet pass for a confirmed registration using the appropriate generator."""

    def __init__(
        self,
        registration_repo: IRegistrationRepository,
        generators: dict[str, IWalletPassGenerator],
    ) -> None:
        self._repo = registration_repo
        self._generators = generators

    def execute(
        self,
        *,
        registration_id: uuid.UUID,
        user_id: uuid.UUID,
        pass_type: str,
    ) -> WalletPassEntity:
        """Validate inputs, check status, delegate to generator."""
        if pass_type not in self._generators:
            raise ValueError(f"pass_type must be one of {sorted(self._generators)}")

        registration = self._repo.get_by_id_for_user(registration_id, user_id)

        if registration.status != "confirmed":
            raise InvalidRegistrationStatusError(
                "Wallet passes can only be generated for confirmed registrations."
            )

        return self._generators[pass_type].generate(registration)
