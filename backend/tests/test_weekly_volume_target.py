import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    session = {"username": main.APP_USERNAME}


class MemoryWeeklyVolume:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT s.report_date,c.operator"):
            if parameters != ("2026-10-01", "2026-10-31"):
                raise AssertionError(f"Unexpected sales parameters: {parameters}")
            return SimpleNamespace(fetchall=lambda: [{
                "report_date": date(2026, 10, 1),
                "operator": "SETU",
                "so": 120,
                "actual": 100,
            }])
        if statement.startswith("SELECT so FROM monthly_so_targets"):
            if parameters != ("2026-10-01", "2026-10-01"):
                raise AssertionError(f"Unexpected target parameters: {parameters}")
            return SimpleNamespace(fetchall=lambda: [{"so": 500}])
        raise AssertionError(f"Unexpected SQL in weekly volume test: {statement}")


class WeeklyVolumeTargetTests(unittest.TestCase):
    def test_returns_target_entered_on_monthly_page(self):
        with patch.object(main, "db", return_value=MemoryWeeklyVolume()):
            result = main.weekly_volume(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        self.assertEqual(result["totals"]["so"], 120)
        self.assertEqual(result["totals"]["target"], 500)
        self.assertEqual(result["totals"]["actual"], 100)
        self.assertEqual(
            result["detail_weeks"],
            [{
                "week": 40,
                "label": "Week 40",
                "start_date": "2026-10-01",
                "end_date": "2026-10-04",
                "so": 120.0,
                "actual": 100.0,
                "diff": -20.0,
                "achievement": 100 / 120 * 100,
            }, {
                "week": 41,
                "label": "Week 41",
                "start_date": "2026-10-05",
                "end_date": "2026-10-11",
                "so": 0.0,
                "actual": 0.0,
                "diff": 0.0,
                "achievement": 0,
            }, {
                "week": 42,
                "label": "Week 42",
                "start_date": "2026-10-12",
                "end_date": "2026-10-18",
                "so": 0.0,
                "actual": 0.0,
                "diff": 0.0,
                "achievement": 0,
            }, {
                "week": 43,
                "label": "Week 43",
                "start_date": "2026-10-19",
                "end_date": "2026-10-25",
                "so": 0.0,
                "actual": 0.0,
                "diff": 0.0,
                "achievement": 0,
            }, {
                "week": 44,
                "label": "Week 44",
                "start_date": "2026-10-26",
                "end_date": "2026-10-31",
                "so": 0.0,
                "actual": 0.0,
                "diff": 0.0,
                "achievement": 0,
            }],
        )


if __name__ == "__main__":
    unittest.main()
