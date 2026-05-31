"""Unit tests for custom DRF permission classes."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_request(
    *, org_roles: dict, data: dict | None = None, query_params: dict | None = None
) -> MagicMock:
    """Build a mock DRF request with org_roles on the user."""
    request = MagicMock()
    request.user.org_roles = org_roles
    # no JWT token object - use the direct org_roles path
    del request.user.token
    request.data = data or {}
    request.query_params = query_params or {}
    return request


def _make_view(*, kwargs: dict | None = None) -> MagicMock:
    """Build a mock view with optional kwargs."""
    view = MagicMock()
    view.org_id = None
    view.kwargs = kwargs or {}
    return view


def test_org_manager_can_batch_checkin() -> None:
    """IsOrgManager grants access when user has manager role for the org in request.data."""
    from apps.common.permissions import IsOrgManager

    org_id = "org-abc"
    request = _make_request(
        org_roles={org_id: "manager"},
        data={"organization_id": org_id},
    )
    view = _make_view()

    perm = IsOrgManager()
    assert perm.has_permission(request, view) is True


def test_non_member_denied_stats() -> None:
    """IsOrgMember denies access when org_roles is empty."""
    from apps.common.permissions import IsOrgMember

    org_id = "org-xyz"
    request = _make_request(
        org_roles={},
        query_params={"organization_id": org_id},
    )
    view = _make_view()

    perm = IsOrgMember()
    assert perm.has_permission(request, view) is False
