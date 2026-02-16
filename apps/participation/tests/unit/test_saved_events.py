"""Tests for SavedEvent model and API endpoints (items 13+16)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from apps.participation.infrastructure.saved_events_models import SavedEvent


class TestSavedEventModel:
    """Basic model-level tests for SavedEvent."""

    def test_saved_event_has_expected_fields(self) -> None:
        """SavedEvent must have id, user_id, event_id, saved_at fields."""
        assert hasattr(SavedEvent, "user_id")
        assert hasattr(SavedEvent, "event_id")
        assert hasattr(SavedEvent, "saved_at")

    def test_saved_event_meta_table_name(self) -> None:
        """SavedEvent must use the participation schema."""
        assert SavedEvent._meta.db_table == '"participation"."saved_event"'

    def test_saved_event_unique_together(self) -> None:
        """SavedEvent must enforce unique (user_id, event_id) constraint."""
        constraint_fields = [list(constraint.fields) for constraint in SavedEvent._meta.constraints]
        assert ["user_id", "event_id"] in constraint_fields


class TestSavedEventViewLogic:
    """Unit tests for SavedEvent endpoint views with mocked ORM."""

    def _make_request(self, method: str, path: str, data: dict | None = None) -> object:
        """Build an authenticated DRF request with JSON parsers attached."""
        from rest_framework.parsers import JSONParser
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        if method == "get":
            django_request = factory.get(path)
        elif method == "post":
            django_request = factory.post(path, data=data, format="json")
        else:
            django_request = factory.delete(path)

        request = Request(django_request, parsers=[JSONParser()])
        fake_user = MagicMock()
        fake_user.id = str(uuid.uuid4())
        fake_user.is_authenticated = True
        request._user = fake_user
        return request

    def test_list_saved_events_returns_200(self) -> None:
        """GET /saved-events/ must return 200 with a list."""
        from apps.participation.presentation.views import SavedEventListCreateView

        request = self._make_request("get", "/api/v1/saved-events/")

        with patch("apps.participation.presentation.views.SavedEvent") as mock_model:
            mock_qs = MagicMock()
            mock_model.objects.filter.return_value.order_by.return_value = []
            mock_model.objects.filter.return_value = mock_qs
            mock_qs.order_by.return_value = []

            view = SavedEventListCreateView()
            view.permission_classes = []
            view.authentication_classes = []
            view.kwargs = {}
            view.args = ()
            view.request = request
            view.format_kwarg = None
            view.headers = {}

            response = view.get(request)

        assert response.status_code == 200

    def test_save_event_returns_201(self) -> None:
        """POST /saved-events/ must return 201 when event saved successfully."""
        from apps.participation.presentation.views import SavedEventListCreateView

        event_id = uuid.uuid4()
        request = self._make_request("post", "/api/v1/saved-events/", {"event_id": str(event_id)})

        with patch("apps.participation.presentation.views.SavedEvent") as mock_model:
            mock_instance = MagicMock()
            mock_instance.id = uuid.uuid4()
            mock_instance.event_id = event_id
            mock_instance.saved_at = MagicMock()
            mock_instance.saved_at.isoformat.return_value = "2026-01-01T00:00:00Z"
            # filter().exists() must return False to skip the duplicate check
            mock_model.objects.filter.return_value.exists.return_value = False
            mock_model.objects.create.return_value = mock_instance

            view = SavedEventListCreateView()
            view.permission_classes = []
            view.authentication_classes = []
            view.kwargs = {}
            view.args = ()
            view.request = request
            view.format_kwarg = None
            view.headers = {}

            response = view.post(request)

        assert response.status_code == 201

    def test_unsave_event_returns_200(self) -> None:
        """DELETE /saved-events/{event_id}/ must return 200 on success."""
        from apps.participation.presentation.views import SavedEventDeleteView

        event_id = uuid.uuid4()
        user_id = uuid.uuid4()
        request = self._make_request("delete", f"/api/v1/saved-events/{event_id}/")
        request._user.id = str(user_id)

        with patch("apps.participation.presentation.views.SavedEvent") as mock_model:
            mock_qs = MagicMock()
            mock_qs.delete.return_value = (1, {})
            mock_model.objects.filter.return_value = mock_qs

            view = SavedEventDeleteView()
            view.permission_classes = []
            view.authentication_classes = []
            view.kwargs = {}
            view.args = ()
            view.request = request
            view.format_kwarg = None
            view.headers = {}

            response = view.delete(request, event_id=event_id)

        assert response.status_code == 200

    def test_save_event_missing_event_id_raises_validation_error(self) -> None:
        """POST /saved-events/ without event_id raises DRF ValidationError (400)."""
        from rest_framework.exceptions import ValidationError

        from apps.participation.presentation.views import SavedEventListCreateView

        request = self._make_request("post", "/api/v1/saved-events/", {})

        view = SavedEventListCreateView()
        view.permission_classes = []
        view.authentication_classes = []
        view.kwargs = {}
        view.args = ()
        view.request = request
        view.format_kwarg = None
        view.headers = {}

        # DRF raises ValidationError which its exception handler converts to 400
        with pytest.raises(ValidationError):
            view.post(request)
