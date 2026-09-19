from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from releaseplanner import PlanningError, plan_release


PUBLIC_SPEC = {
    "budget": 12,
    "risk_limit": 6,
    "team_capacities": {"backend": 4, "mobile": 3, "data": 2},
    "required_categories": ["security", "experience"],
    "mandatory": ["foundation"],
    "initiatives": [
        {"id": "foundation", "value": 3, "cost": 1, "risk": 0, "category": "platform", "team_effort": {"backend": 1}, "requires": [], "conflicts": []},
        {"id": "auth", "value": 9, "cost": 3, "risk": 2, "category": "security", "team_effort": {"backend": 2}, "requires": ["foundation"], "conflicts": []},
        {"id": "passkeys", "value": 10, "cost": 4, "risk": 1, "category": "security", "team_effort": {"mobile": 2}, "requires": ["auth"], "conflicts": []},
        {"id": "offline", "value": 8, "cost": 3, "risk": 2, "category": "experience", "team_effort": {"mobile": 2}, "requires": [], "conflicts": ["sync"]},
        {"id": "sync", "value": 11, "cost": 5, "risk": 3, "category": "experience", "team_effort": {"backend": 2, "data": 1}, "requires": ["foundation"], "conflicts": []},
        {"id": "insights", "value": 7, "cost": 3, "risk": 2, "category": "analytics", "team_effort": {"data": 2}, "requires": [], "conflicts": []},
        {"id": "polish", "value": 6, "cost": 2, "risk": 1, "category": "experience", "team_effort": {"mobile": 1}, "requires": [], "conflicts": []}
    ]
}


class PlannerTests(unittest.TestCase):
    def test_public_plan_is_optimal_and_deterministic(self):
        first = plan_release(PUBLIC_SPEC)
        second = plan_release(PUBLIC_SPEC)
        self.assertEqual(first, second)
        self.assertEqual(sorted(first["selected"]), first["selected"])

    def test_rejects_boolean_budget(self):
        with self.assertRaises(PlanningError):
            plan_release(dict(PUBLIC_SPEC, budget=True))

    def test_impossible_mandatory_plan(self):
        with self.assertRaises(PlanningError):
            plan_release(dict(PUBLIC_SPEC, budget=0))


if __name__ == "__main__":
    unittest.main()
