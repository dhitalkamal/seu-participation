"""HTTP adapter for fetching org plan data from the management-service."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid


# registration cap per plan - matches what's advertised on the pricing page
PLAN_REGISTRATION_CAPS: dict[str, int | None] = {
    "free": 100,
    "starter": 1000,
    "pro": None,
    "ngo": None,
    "enterprise": None,
}


class OrgPlan:
    """Value object representing an org's current subscription plan."""

    def __init__(self, plan: str, plan_expires_at: str | None = None) -> None:
        self.plan = plan
        self.plan_expires_at = plan_expires_at

    @property
    def registration_cap(self) -> int | None:
        """Max registrations per event, or None for unlimited."""
        return PLAN_REGISTRATION_CAPS.get(self.plan)


class HttpPlanClient:
    """Calls the management-service to look up an org's plan."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_org_plan(self, org_id: uuid.UUID) -> OrgPlan:
        """
        Fetch the org's subscription plan from management-service.

        Falls back to 'free' if the org is not found or the service is down.
        """
        url = f"{self._base_url}/api/v1/organizations/internal/orgs/{org_id}/plan/"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
                return OrgPlan(
                    plan=data.get("plan", "free"),
                    plan_expires_at=data.get("plan_expires_at"),
                )
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError):
            return OrgPlan(plan="free")
