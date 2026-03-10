"""Unit tests for garq.py — all API calls are mocked, no real Garmin credentials needed."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import garq.py as a module (shebang line is just a comment, no problem)
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location("garq", Path(__file__).parent / "garq.py")
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["garq"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_fmt_duration = _mod._fmt_duration
_fmt_pace = _mod._fmt_pace
_safe = _mod._safe
cmd_today = _mod.cmd_today
cmd_sleep = _mod.cmd_sleep
cmd_activities = _mod.cmd_activities
cmd_activity = _mod.cmd_activity
cmd_hrv = _mod.cmd_hrv
cmd_weight = _mod.cmd_weight
cmd_steps = _mod.cmd_steps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def args(**kwargs: Any) -> argparse.Namespace:
    """Build a fake argparse.Namespace with raw=False as default."""
    defaults: dict[str, Any] = {"raw": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def mock_api(**methods: Any) -> MagicMock:
    """Return a MagicMock with the given methods pre-configured."""
    api = MagicMock()
    for name, value in methods.items():
        if callable(value) and isinstance(value, Exception):
            getattr(api, name).side_effect = value
        else:
            getattr(api, name).return_value = value
    return api


# ---------------------------------------------------------------------------
# _fmt_duration
# ---------------------------------------------------------------------------


class TestFmtDuration:
    def test_none(self) -> None:
        assert _fmt_duration(None) == "n/a"

    def test_zero(self) -> None:
        assert _fmt_duration(0) == "0m"

    def test_minutes_only(self) -> None:
        assert _fmt_duration(30 * 60) == "30m"

    def test_hours_and_minutes(self) -> None:
        assert _fmt_duration(90 * 60) == "1h 30m"

    def test_exact_hour(self) -> None:
        assert _fmt_duration(3600) == "1h 00m"

    def test_float_input(self) -> None:
        assert _fmt_duration(3661.9) == "1h 01m"

    def test_large(self) -> None:
        assert _fmt_duration(8 * 3600 + 7 * 60) == "8h 07m"


# ---------------------------------------------------------------------------
# _fmt_pace
# ---------------------------------------------------------------------------


class TestFmtPace:
    def test_none(self) -> None:
        assert _fmt_pace(None) == "n/a"

    def test_zero(self) -> None:
        assert _fmt_pace(0) == "n/a"

    def test_5min_per_km(self) -> None:
        # 5 min/km = 300 s/km = 0.3 s/m
        assert _fmt_pace(0.3) == "5:00/km"

    def test_sub_4(self) -> None:
        # 3:30/km = 210 s/km = 0.21 s/m
        assert _fmt_pace(0.21) == "3:30/km"

    def test_seconds_round(self) -> None:
        # 4:05/km = 245 s/km = 0.245 s/m
        assert _fmt_pace(0.245) == "4:05/km"


# ---------------------------------------------------------------------------
# _safe
# ---------------------------------------------------------------------------


class TestSafe:
    def test_single_key(self) -> None:
        assert _safe({"a": 1}, "a") == 1

    def test_nested(self) -> None:
        assert _safe({"a": {"b": 42}}, "a", "b") == 42

    def test_missing_key_returns_default(self) -> None:
        assert _safe({"a": 1}, "z") is None
        assert _safe({"a": 1}, "z", default=0) == 0

    def test_none_input(self) -> None:
        assert _safe(None, "a") is None

    def test_non_dict_mid_path(self) -> None:
        assert _safe({"a": "string"}, "a", "b") is None

    def test_empty_dict(self) -> None:
        assert _safe({}, "a") is None

    def test_deeply_nested(self) -> None:
        d = {"x": {"y": {"z": 99}}}
        assert _safe(d, "x", "y", "z") == 99
        assert _safe(d, "x", "y", "missing") is None


# ---------------------------------------------------------------------------
# cmd_today
# ---------------------------------------------------------------------------


class TestCmdToday:
    def _api(self) -> MagicMock:
        return mock_api(
            get_user_summary={
                "totalSteps": 8432,
                "dailyStepGoal": 10000,
                "totalDistanceMeters": 6700,
                "totalKilocalories": 2156,
                "activeKilocalories": 456,
                "floorsAscended": 12,
                "restingHeartRate": 58,
                "averageHeartRate": 72,
                "maxHeartRate": 142,
                "minHeartRate": 48,
                "averageStressLevel": 24,
                "maxStressLevel": 55,
                "bodyBatteryMostRecentValue": 45,
                "bodyBatteryHighestValue": 87,
                "bodyBatteryLowestValue": 23,
                "bodyBatteryChargedValue": 12,
                "bodyBatteryDrainedValue": 8,
            },
            get_stats={"restingHeartRate": 58},
            get_heart_rates={},
            get_body_battery=[],
            get_stress_data={},
            get_sleep_data={
                "dailySleepDTO": {
                    "sleepTimeSeconds": 7 * 3600 + 32 * 60,
                    "deepSleepSeconds": 1 * 3600 + 45 * 60,
                    "lightSleepSeconds": 4 * 3600 + 12 * 60,
                    "remSleepSeconds": 1 * 3600 + 35 * 60,
                    "awakeSleepSeconds": 12 * 60,
                }
            },
            get_hrv_data={
                "hrvSummary": {
                    "lastNightAvg": 48,
                    "weeklyAvg": 52,
                    "status": "BALANCED",
                }
            },
            get_respiration_data={},
            get_spo2_data={"averageSpO2": 96, "lowestSpO2": 92},
        )

    def test_steps_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "8,432 / 10,000 (84%)" in out

    def test_distance_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "6.7 km" in out

    def test_calories_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "2156 kcal" in out
        assert "active: 456" in out

    def test_hr_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "resting 58 bpm" in out
        assert "max 142" in out

    def test_body_battery_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "current 45" in out
        assert "peak 87" in out
        assert "low 23" in out
        assert "+12 charged" in out
        assert "-8 drained" in out

    def test_stress_low_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "avg 24 (low)" in out

    def test_spo2_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        # spo2_today mock returns averageSpO2/lowestSpO2
        assert "96%" in out
        assert "92%" in out

    def test_sleep_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "7h 32m" in out
        assert "deep 1h 45m" in out
        assert "REM 1h 35m" in out

    def test_hrv_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_today(self._api(), args())
        out = capsys.readouterr().out
        assert "last night 48 ms" in out
        assert "BALANCED" in out

    def test_api_failure_graceful(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Optional endpoints failing should not crash the command."""
        api = mock_api(
            get_user_summary={"totalSteps": 1000, "dailyStepGoal": 10000},
            get_stats={},
        )
        api.get_heart_rates.side_effect = Exception("network error")
        api.get_body_battery.side_effect = Exception("network error")
        api.get_stress_data.side_effect = Exception("network error")
        api.get_sleep_data.side_effect = Exception("network error")
        api.get_hrv_data.side_effect = Exception("network error")
        api.get_respiration_data.side_effect = Exception("network error")
        cmd_today(api, args())
        out = capsys.readouterr().out
        assert "1,000" in out  # steps still printed

    def test_stress_levels(self, capsys: pytest.CaptureFixture[str]) -> None:
        for avg, expected in [(10, "low"), (35, "medium"), (60, "high"), (80, "very high")]:
            api = mock_api(
                get_user_summary={"averageStressLevel": avg},
                get_stats={},
                get_heart_rates={},
                get_body_battery=[],
                get_stress_data={},
                get_sleep_data={},
                get_hrv_data={},
                get_respiration_data={},
            )
            cmd_today(api, args())
            out = capsys.readouterr().out
            assert expected in out, f"avg={avg} should produce level '{expected}'"


# ---------------------------------------------------------------------------
# cmd_sleep
# ---------------------------------------------------------------------------


class TestCmdSleep:
    def _sleep_response(self, total_s: int = 27000) -> dict[str, Any]:
        return {
            "dailySleepDTO": {
                "sleepTimeSeconds": total_s,
                "deepSleepSeconds": 5400,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 600,
                "sleepScore": 82,
            }
        }

    def test_table_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_sleep_data=self._sleep_response())
        cmd_sleep(api, args(days=1))
        out = capsys.readouterr().out
        assert "Total" in out
        assert "Deep" in out
        assert "REM" in out

    def test_duration_formatted(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_sleep_data=self._sleep_response(total_s=7 * 3600 + 30 * 60))
        cmd_sleep(api, args(days=1))
        out = capsys.readouterr().out
        assert "7h 30m" in out

    def test_no_data_row(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_sleep_data={})
        cmd_sleep(api, args(days=1))
        out = capsys.readouterr().out
        assert "no data" in out

    def test_api_error_row(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = MagicMock()
        api.get_sleep_data.side_effect = Exception("boom")
        cmd_sleep(api, args(days=1))
        out = capsys.readouterr().out
        assert "error" in out

    def test_score_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_sleep_data=self._sleep_response())
        cmd_sleep(api, args(days=1))
        out = capsys.readouterr().out
        assert "82" in out


# ---------------------------------------------------------------------------
# cmd_activities
# ---------------------------------------------------------------------------


class TestCmdActivities:
    def _run(self) -> dict[str, Any]:
        return {
            "startTimeLocal": "2026-03-10 07:00:00",
            "activityType": {"typeKey": "running"},
            "activityName": "Morning Run",
            "duration": 1800.0,  # 30 min
            "distance": 5000.0,  # 5 km
            "averageHR": 155,
            "maxHR": 172,
            "calories": 420,
            "elevationGain": 45.0,
        }

    def _ride(self) -> dict[str, Any]:
        return {
            "startTimeLocal": "2026-03-09 10:00:00",
            "activityType": {"typeKey": "cycling"},
            "activityName": "cycling",
            "duration": 3600.0,  # 1h
            "distance": 30000.0,  # 30 km
            "averageHR": 140,
            "maxHR": 165,
            "calories": 800,
            "elevationGain": 200.0,
        }

    def test_run_pace(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[self._run()])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        # 1800s / 5000m = 0.36 s/m = 360 s/km = 6:00/km
        assert "6:00/km" in out

    def test_ride_speed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[self._ride()])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        # 30km / 1h = 30.0 km/h
        assert "30.0 km/h" in out

    def test_hr_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[self._run()])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        assert "HR 155/172" in out

    def test_elevation_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[self._run()])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        assert "+45m" in out

    def test_empty_activities(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        assert "Recent Activities (0)" in out

    def test_date_truncated(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_activities=[self._run()])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        assert "2026-03-10" in out

    def test_days_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        old = dict(self._run())
        old["startTimeLocal"] = "2020-01-01 07:00:00"  # very old
        api = mock_api(get_activities=[self._run(), old])
        cmd_activities(api, args(limit=10, days=7))
        out = capsys.readouterr().out
        assert "Activities: last 7 days (1)" in out

    def test_walking_pace(self, capsys: pytest.CaptureFixture[str]) -> None:
        walk = {
            "startTimeLocal": "2026-03-10 09:00:00",
            "activityType": {"typeKey": "walking"},
            "activityName": "Morning Walk",
            "duration": 3600.0,  # 1h
            "distance": 5000.0,  # 5km → 12:00/km
        }
        api = mock_api(get_activities=[walk])
        cmd_activities(api, args(limit=10, days=None))
        out = capsys.readouterr().out
        assert "12:00/km" in out


# ---------------------------------------------------------------------------
# cmd_hrv
# ---------------------------------------------------------------------------


class TestCmdHrv:
    def _hrv_response(self) -> dict[str, Any]:
        return {
            "hrvSummary": {
                "lastNightAvg": 48,
                "lastNight5MinHigh": 62,
                "weeklyAvg": 52,
                "baseline": {"balancedLow": 44, "balancedUpper": 58},
                "status": "BALANCED",
            }
        }

    def test_header_printed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_hrv_data=self._hrv_response())
        cmd_hrv(api, args(days=1))
        out = capsys.readouterr().out
        assert "HRV" in out
        assert "Last night" in out
        assert "Weekly avg" in out
        assert "5-min high" in out

    def test_values_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_hrv_data=self._hrv_response())
        cmd_hrv(api, args(days=1))
        out = capsys.readouterr().out
        assert "48" in out
        assert "52" in out
        assert "62" in out
        assert "BALANCED" in out
        assert "44-58" in out

    def test_api_error_row(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = MagicMock()
        api.get_hrv_data.side_effect = Exception("fail")
        cmd_hrv(api, args(days=1))
        out = capsys.readouterr().out
        assert "error" in out


# ---------------------------------------------------------------------------
# cmd_weight
# ---------------------------------------------------------------------------


class TestCmdWeight:
    def _entry(self, weight_g: float = 80000, fat: float = 18.5) -> dict[str, Any]:
        return {
            "summaryDate": "2026-03-10",
            "allWeightMetrics": [
                {
                    "weight": weight_g,
                    "bmi": 24.1,
                    "bodyFat": fat,
                    "boneMass": 3200.0,  # grams
                }
            ],
        }

    def test_weight_grams_converted(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_weigh_ins={"dailyWeightSummaries": [self._entry(80000)]})
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "80.0 kg" in out

    def test_weight_already_kg(self, capsys: pytest.CaptureFixture[str]) -> None:
        # some integrations store kg directly (< 1000)
        api = mock_api(get_weigh_ins={"dailyWeightSummaries": [self._entry(79.5)]})
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "79.5 kg" in out

    def test_bone_grams_converted(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_weigh_ins={"dailyWeightSummaries": [self._entry()]})
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "3.20" in out  # 3200g → 3.20 kg

    def test_fat_pct_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_weigh_ins={"dailyWeightSummaries": [self._entry(fat=18.5)]})
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "18.5%" in out

    def test_no_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(
            get_weigh_ins={"dailyWeightSummaries": []},
            get_daily_weigh_ins=[],
        )
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "no weight data" in out

    def test_fallback_to_daily_weigh_ins(self, capsys: pytest.CaptureFixture[str]) -> None:
        """get_weigh_ins returns empty → falls back to get_daily_weigh_ins."""
        api = mock_api(
            get_weigh_ins={"dailyWeightSummaries": []},
            get_daily_weigh_ins=[
                {"calendarDate": "2026-03-10", "weight": 81000, "bmi": 24.5}
            ],
        )
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "81.0 kg" in out

    def test_bmi_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_weigh_ins={"dailyWeightSummaries": [self._entry()]})
        cmd_weight(api, args(days=7))
        out = capsys.readouterr().out
        assert "24.1" in out


# ---------------------------------------------------------------------------
# cmd_activity
# ---------------------------------------------------------------------------


class TestCmdActivity:
    def _detail(self) -> dict[str, Any]:
        return {
            "activityName": "Morning Run",
            "activityTypeDTO": {"typeKey": "running"},
            "summaryDTO": {
                "startTimeLocal": "2026-03-10 07:15:00",
                "duration": 1800.0,
                "distance": 5000.0,
                "averageHR": 155.0,
                "maxHR": 172.0,
                "calories": 420.0,
                "elevationGain": 45.0,
            },
        }

    def _zones(self) -> list[dict[str, Any]]:
        # real API: no percentageInZone, only secsInZone + zoneNumber
        return [
            {"zoneNumber": 1, "secsInZone": 120},
            {"zoneNumber": 2, "secsInZone": 300},
            {"zoneNumber": 3, "secsInZone": 600},
            {"zoneNumber": 4, "secsInZone": 660},
            {"zoneNumber": 5, "secsInZone": 120},
        ]

    def test_basic_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(
            get_activity=self._detail(),
            get_activity_hr_in_timezones=self._zones(),
            get_activity_splits=[],
        )
        cmd_activity(api, args(activity_id=12345678))
        out = capsys.readouterr().out
        assert "Morning Run" in out
        assert "running" in out
        assert "5.00 km" in out
        assert "6:00/km" in out  # 1800s / 5000m
        assert "155" in out
        assert "172" in out

    def test_hr_zones_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(
            get_activity=self._detail(),
            get_activity_hr_in_timezones=self._zones(),
            get_activity_splits=[],
        )
        cmd_activity(api, args(activity_id=12345678))
        out = capsys.readouterr().out
        assert "HR Zones" in out
        assert "Zone 3" in out
        # zone 4: 660 / 1800 total = 36.7% → rounds to 37%
        assert "37%" in out

    def test_degenerate_laps_skipped(self, capsys: pytest.CaptureFixture[str]) -> None:
        laps = [
            {"duration": 360.0, "distance": 1000.0, "averageHR": 150},
            {"duration": 0.0, "distance": 0.0, "averageHR": 105},    # zero distance/duration
            {"duration": 14.0, "distance": 3.16, "averageHR": 105},  # real stop-lap: <10m, <30s
        ]
        api = mock_api(
            get_activity=self._detail(),
            get_activity_hr_in_timezones=[],
            get_activity_splits={"lapDTOs": laps},
        )
        cmd_activity(api, args(activity_id=12345678))
        out = capsys.readouterr().out
        assert "Laps (1)" in out  # both degenerate laps filtered out

    def test_laps_displayed(self, capsys: pytest.CaptureFixture[str]) -> None:
        laps = [
            {"duration": 360.0, "distance": 1000.0, "averageHR": 150},
            {"duration": 360.0, "distance": 1000.0, "averageHR": 158},
        ]
        api = mock_api(
            get_activity=self._detail(),
            get_activity_hr_in_timezones=[],
            get_activity_splits={"lapDTOs": laps},
        )
        cmd_activity(api, args(activity_id=12345678))
        out = capsys.readouterr().out
        assert "Laps (2)" in out
        assert "6:00/km" in out

    def test_api_failure_exits(self) -> None:
        api = MagicMock()
        api.get_activity.side_effect = Exception("not found")
        with pytest.raises(SystemExit):
            cmd_activity(api, args(activity_id=99999))

    def test_raw_dumps_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(
            get_activity=self._detail(),
            get_activity_hr_in_timezones=[],
            get_activity_splits=[],
        )
        cmd_activity(api, args(activity_id=12345678, raw=True))
        out = capsys.readouterr().out
        import json

        parsed = json.loads(out)
        assert parsed["activityName"] == "Morning Run"


# ---------------------------------------------------------------------------
# cmd_steps
# ---------------------------------------------------------------------------


class TestCmdSteps:
    def _step_data(self) -> list[dict[str, Any]]:
        return [
            {"calendarDate": "2026-03-08", "totalSteps": 8500, "stepGoal": 10000, "totalDistance": 6800},
            {"calendarDate": "2026-03-09", "totalSteps": 12300, "stepGoal": 10000, "totalDistance": 9800},
            {"calendarDate": "2026-03-10", "totalSteps": 5200, "stepGoal": 10000, "totalDistance": 4100},
        ]

    def test_daily_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_daily_steps=self._step_data())
        cmd_steps(api, args(days=3, period="day"))
        out = capsys.readouterr().out
        assert "8,500" in out
        assert "12,300" in out
        assert "5,200" in out
        assert "Total" in out
        assert "Calories" not in out  # column removed — API doesn't provide it

    def test_weekly_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_daily_steps=self._step_data())
        cmd_steps(api, args(days=3, period="week"))
        out = capsys.readouterr().out
        # ISO weeks: 2026-03-08 is Sunday (end of W10); 2026-03-09/10 are W11
        assert "W10" in out
        assert "W11" in out
        assert "8,500" in out
        assert "17,500" in out  # 12300+5200
        # current week (W11 as of 2026-03-10) should be marked partial
        assert "W11*" in out

    def test_monthly_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_daily_steps=self._step_data())
        cmd_steps(api, args(days=3, period="month"))
        out = capsys.readouterr().out
        assert "2026-03" in out
        assert "26,000" in out

    def test_no_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        api = mock_api(get_daily_steps=[])
        cmd_steps(api, args(days=7, period="day"))
        out = capsys.readouterr().out
        assert "no step data" in out

    def test_api_failure_exits(self) -> None:
        api = MagicMock()
        api.get_daily_steps.side_effect = Exception("boom")
        with pytest.raises(SystemExit):
            cmd_steps(api, args(days=7, period="day"))
