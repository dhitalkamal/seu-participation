"""Unit tests for InternalParticipationContextView."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory

from apps.participation.presentation.views import InternalParticipationContextView

_REPO_PATH = "apps.participation.infrastructure.repositories.DjangoParticipationContextRepository"


def _view():
    return InternalParticipationContextView.as_view()


def test_get_returns_404_when_no_context_exists():
    """GET returns 404 when no context row exists for the given event/user pair."""
    factory = RequestFactory()
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_repo = MagicMock()
    mock_repo.return_value.get_context.return_value = None
    request = factory.get(f"/internal/participation-context/{event_id}/{user_id}/")
    with patch(_REPO_PATH, mock_repo):
        response = _view()(request, event_id=event_id, user_id=user_id)
    assert response.status_code == 404


def test_get_returns_participation_type_when_context_exists():
    """GET returns participation_type when a context row exists."""
    factory = RequestFactory()
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_repo = MagicMock()
    mock_repo.return_value.get_context.return_value = "attendee"
    request = factory.get(f"/internal/participation-context/{event_id}/{user_id}/")
    with patch(_REPO_PATH, mock_repo):
        response = _view()(request, event_id=event_id, user_id=user_id)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["participation_type"] == "attendee"


def test_post_calls_set_context_and_returns_200():
    """POST calls set_context and returns 200 with participation_type."""
    factory = RequestFactory()
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_repo = MagicMock()
    body = json.dumps({"participation_type": "volunteer"}).encode()
    request = factory.post(
        f"/internal/participation-context/{event_id}/{user_id}/",
        data=body,
        content_type="application/json",
    )
    with patch(_REPO_PATH, mock_repo):
        response = _view()(request, event_id=event_id, user_id=user_id)
    assert response.status_code == 200
    mock_repo.return_value.set_context.assert_called_once_with(event_id, user_id, "volunteer")
    data = json.loads(response.content)
    assert data["participation_type"] == "volunteer"


def test_post_returns_400_when_participation_type_missing():
    """POST returns 400 when participation_type is absent from request body."""
    factory = RequestFactory()
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_repo = MagicMock()
    body = json.dumps({}).encode()
    request = factory.post(
        f"/internal/participation-context/{event_id}/{user_id}/",
        data=body,
        content_type="application/json",
    )
    with patch(_REPO_PATH, mock_repo):
        response = _view()(request, event_id=event_id, user_id=user_id)
    assert response.status_code == 400
