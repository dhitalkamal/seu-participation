"""Unit tests for the volunteer.application.approved consumer handler."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

_CONTEXT_REPO_PATH = (
    "apps.participation.infrastructure.consumer.DjangoParticipationContextRepository"
)


def test_handle_volunteer_approved_sets_volunteer_context():
    """volunteer.application.approved sets participation context to 'volunteer'."""
    from apps.participation.infrastructure.consumer import _handle_volunteer_approved

    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    mock_repo = MagicMock()

    with patch(_CONTEXT_REPO_PATH, mock_repo):
        _handle_volunteer_approved({"user_id": str(user_id), "event_id": str(event_id)})

    mock_repo.return_value.set_context.assert_called_once_with(event_id, user_id, "volunteer")


def test_handle_volunteer_approved_missing_user_id_logs_warning():
    """Missing user_id logs a warning and does not call set_context."""
    from apps.participation.infrastructure.consumer import _handle_volunteer_approved

    mock_repo = MagicMock()
    with (
        patch(_CONTEXT_REPO_PATH, mock_repo),
        patch("apps.participation.infrastructure.consumer.logger") as mock_log,
    ):
        _handle_volunteer_approved({"event_id": str(uuid.uuid4())})

    mock_repo.return_value.set_context.assert_not_called()
    mock_log.warning.assert_called_once()


def test_handle_volunteer_approved_missing_event_id_logs_warning():
    """Missing event_id logs a warning and does not call set_context."""
    from apps.participation.infrastructure.consumer import _handle_volunteer_approved

    mock_repo = MagicMock()
    with (
        patch(_CONTEXT_REPO_PATH, mock_repo),
        patch("apps.participation.infrastructure.consumer.logger") as mock_log,
    ):
        _handle_volunteer_approved({"user_id": str(uuid.uuid4())})

    mock_repo.return_value.set_context.assert_not_called()
    mock_log.warning.assert_called_once()
