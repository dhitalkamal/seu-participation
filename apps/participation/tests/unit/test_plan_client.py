"""Unit tests for plan client and registration cap enforcement."""

from __future__ import annotations

from apps.participation.infrastructure.plan_client import PLAN_REGISTRATION_CAPS, OrgPlan


class TestOrgPlan:
    """Verify registration caps match pricing page claims."""

    def test_free_plan_cap_is_100(self) -> None:
        plan = OrgPlan(plan="free")
        assert plan.registration_cap == 100

    def test_starter_plan_cap_is_1000(self) -> None:
        plan = OrgPlan(plan="starter")
        assert plan.registration_cap == 1000

    def test_pro_plan_unlimited(self) -> None:
        plan = OrgPlan(plan="pro")
        assert plan.registration_cap is None

    def test_ngo_plan_unlimited(self) -> None:
        plan = OrgPlan(plan="ngo")
        assert plan.registration_cap is None

    def test_enterprise_plan_unlimited(self) -> None:
        plan = OrgPlan(plan="enterprise")
        assert plan.registration_cap is None

    def test_unknown_plan_defaults_to_none(self) -> None:
        plan = OrgPlan(plan="unknown")
        assert plan.registration_cap is None

    def test_all_plans_covered(self) -> None:
        expected = {"free", "starter", "pro", "ngo", "enterprise"}
        assert set(PLAN_REGISTRATION_CAPS.keys()) == expected
