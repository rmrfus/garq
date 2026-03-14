#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["garminconnect", "keyring"]
# ///

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date, timedelta
from typing import Any

import keyring
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

GARTH_HOME = os.path.expanduser("~/.garth")
KEYRING_SERVICE = "garq"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _prompt_mfa() -> str:
    return input("Garmin MFA code: ")


def _load_api() -> Garmin:
    """Return authenticated Garmin API instance, refreshing tokens as needed."""
    api = Garmin()
    try:
        api.login(tokenstore=GARTH_HOME)
        return api
    except Exception:
        pass

    email = keyring.get_password(KEYRING_SERVICE, "email")
    password = keyring.get_password(KEYRING_SERVICE, "password")

    if not email or not password:
        print("First-time setup: enter Garmin Connect credentials.", file=sys.stderr)
        print("They will be stored in the system keychain.", file=sys.stderr)
        email = input("Email: ")
        password = getpass.getpass("Password: ")
        keyring.set_password(KEYRING_SERVICE, "email", email)
        keyring.set_password(KEYRING_SERVICE, "password", password)

    try:
        api = Garmin(email=email, password=password, prompt_mfa=_prompt_mfa)
        api.login()
    except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
        # Clear cached creds so the user can re-enter them next time
        keyring.delete_password(KEYRING_SERVICE, "email")
        keyring.delete_password(KEYRING_SERVICE, "password")
        sys.exit(f"login failed: {e}")

    os.makedirs(GARTH_HOME, exist_ok=True)
    api.garth.dump(GARTH_HOME)
    return api


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "n/a"
    s = int(seconds)
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _fmt_pace(seconds_per_meter: float | None) -> str:
    """Convert s/m to min/km string."""
    if not seconds_per_meter:
        return "n/a"
    spm = seconds_per_meter * 1000
    m, s = divmod(int(spm), 60)
    return f"{m}:{s:02d}/km"


def _inum(v: Any) -> Any:
    """Return int if value is a whole-number float, otherwise return as-is."""
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _activity_label(atype: str, name: str) -> str:
    """Return activity label with type-word deduplicated from name."""
    if not name:
        return atype
    type_words = set(atype.replace("_", " ").lower().split())
    filtered = [w for w in name.split() if w.lower() not in type_words]
    clean = " ".join(filtered).strip()
    if not clean or clean.lower() == name.lower() == atype.lower():
        return atype
    return f"{atype} ({clean})" if clean else atype


_ENDURANCE_CLASS: dict[int, str] = {
    1: "basic",
    2: "intermediate",
    3: "trained",
    4: "well-trained",
    5: "expert",
    6: "superior",
    7: "elite",
}


def _safe(d: Any, *keys: str, default: Any = None) -> Any:
    val: Any = d
    for k in keys:
        if not isinstance(val, dict):
            return default
        val = val.get(k, default)
    return val


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_today(api: Garmin, args: Any) -> None:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    summary = api.get_user_summary(today)
    stats = api.get_stats(today)

    try:
        hr_data = api.get_heart_rates(today)
    except Exception:
        hr_data = {}

    try:
        api.get_body_battery(today, today)
    except Exception:
        pass

    try:
        stress_data = api.get_stress_data(today)
    except Exception:
        stress_data = {}

    try:
        sleep_data = api.get_sleep_data(yesterday)
    except Exception:
        sleep_data = {}

    try:
        hrv_data = api.get_hrv_data(yesterday)
    except Exception:
        hrv_data = {}

    try:
        spo2_today = api.get_spo2_data(today)
    except Exception:
        spo2_today = {}

    try:
        readiness_data = api.get_training_readiness(today)
    except Exception:
        readiness_data = {}

    try:
        training_status_data = api.get_training_status(today)
    except Exception:
        training_status_data = {}

    try:
        endurance_data = api.get_endurance_score(today)
    except Exception:
        endurance_data = {}

    print(f"=== Daily Summary: {today} ===\n")

    # Steps / distance / calories
    steps = _safe(summary, "totalSteps")
    goal = _safe(summary, "dailyStepGoal") or 10000
    dist_m = _safe(summary, "totalDistanceMeters")
    calories = _safe(summary, "totalKilocalories")
    active_cal = _safe(summary, "activeKilocalories")
    floors = _safe(summary, "floorsAscended")

    if steps is not None:
        pct = int(steps / goal * 100) if goal else 0
        print(f"Steps:        {steps:,} / {goal:,} ({pct}%)")
    if dist_m is not None:
        print(f"Distance:     {dist_m / 1000:.1f} km")
    if calories is not None:
        active_str = f" (active: {_inum(active_cal)})" if active_cal is not None else ""
        print(f"Calories:     {_inum(calories)} kcal{active_str}")
    if floors is not None:
        print(f"Floors:       {int(floors)}")

    # Heart rate
    rhr = _safe(summary, "restingHeartRate") or _safe(stats, "restingHeartRate")
    hr_avg = _safe(summary, "averageHeartRate") or _safe(hr_data, "heartRateValues")
    hr_max = _safe(summary, "maxHeartRate")
    hr_min = _safe(summary, "minHeartRate")

    hr_parts: list[str] = []
    if rhr:
        hr_parts.append(f"resting {_inum(rhr)} bpm")
    if hr_avg and not isinstance(hr_avg, list):
        hr_parts.append(f"avg {_inum(hr_avg)}")
    if hr_max:
        hr_parts.append(f"max {_inum(hr_max)}")
    if hr_min:
        hr_parts.append(f"min {_inum(hr_min)}")
    if hr_parts:
        print(f"Heart Rate:   {' | '.join(hr_parts)}")

    # HRV
    hrv_summary = _safe(hrv_data, "hrvSummary")
    if hrv_summary:
        hrv_weekly = _safe(hrv_summary, "weeklyAvg")
        hrv_last = _safe(hrv_summary, "lastNightAvg")
        hrv_status = _safe(hrv_summary, "status")
        parts = []
        if hrv_last is not None:
            parts.append(f"last night {hrv_last} ms")
        if hrv_weekly is not None:
            parts.append(f"weekly avg {hrv_weekly} ms")
        if hrv_status:
            parts.append(f"status: {hrv_status}")
        if parts:
            print(f"HRV:          {' | '.join(parts)}")

    # Body battery — actual level lives in user_summary, not get_body_battery()
    # (charged/drained from get_body_battery are cumulative deltas, not levels)
    bb_current = _safe(summary, "bodyBatteryMostRecentValue")
    bb_high = _safe(summary, "bodyBatteryHighestValue")
    bb_low = _safe(summary, "bodyBatteryLowestValue")
    bb_charged = _safe(summary, "bodyBatteryChargedValue")
    bb_drained = _safe(summary, "bodyBatteryDrainedValue")

    if any(v is not None for v in (bb_current, bb_high, bb_low)):
        parts = []
        if bb_current is not None:
            parts.append(f"current {bb_current}")
        if bb_high is not None:
            parts.append(f"peak {bb_high}")
        if bb_low is not None:
            parts.append(f"low {bb_low}")
        if bb_charged:
            parts.append(f"+{bb_charged} charged")
        if bb_drained:
            parts.append(f"-{bb_drained} drained")
        print(f"Body Battery: {' | '.join(parts)}")

    # Stress
    stress_avg = _safe(stress_data, "avgStressLevel") or _safe(summary, "averageStressLevel")
    stress_max = _safe(stress_data, "maxStressLevel") or _safe(summary, "maxStressLevel")
    if stress_avg is not None:
        level = (
            "low"
            if stress_avg < 26
            else "medium"
            if stress_avg < 51
            else "high"
            if stress_avg < 76
            else "very high"
        )
        stress_str = f"avg {stress_avg} ({level})"
        if stress_max:
            stress_str += f" | max {stress_max}"
        print(f"Stress:       {stress_str}")

    # SpO2 / respiration
    spo2_avg = _safe(spo2_today, "averageSpO2") or _safe(spo2_today, "avgSleepSpO2")
    spo2_low = _safe(spo2_today, "lowestSpO2")
    if spo2_avg is not None:
        spo2_str = f"avg {_inum(spo2_avg)}%"
        if spo2_low:
            spo2_str += f" | low {_inum(spo2_low)}%"
        print(f"SpO2:         {spo2_str}")

    # Training readiness / status
    readiness_score = _safe(readiness_data, "score") or _safe(
        readiness_data, "trainingReadinessScore"
    )
    readiness_level = _safe(readiness_data, "level") or _safe(
        readiness_data, "trainingReadinessLevel"
    )
    t_status = _safe(training_status_data, "mostRecentTrainingStatus") or _safe(
        training_status_data, "trainingStatus"
    )
    endurance_score = _safe(endurance_data, "overallScore")
    endurance_class = _ENDURANCE_CLASS.get(_safe(endurance_data, "classification") or 0, "")
    if readiness_score is not None or t_status or endurance_score is not None:
        r_parts = []
        if readiness_score is not None:
            level_str = f" ({readiness_level})" if readiness_level else ""
            r_parts.append(f"Readiness: {_inum(readiness_score)}/100{level_str}")
        if t_status:
            r_parts.append(f"Status: {t_status}")
        if endurance_score is not None:
            cls_str = f" ({endurance_class})" if endurance_class else ""
            r_parts.append(f"Endurance: {_inum(endurance_score)}{cls_str}")
        print(f"Training:     {' | '.join(r_parts)}")

    # Sleep summary
    sleep_summary = _safe(sleep_data, "dailySleepDTO") or (
        _safe(sleep_data, "sleepTimeSeconds") and sleep_data
    )
    if not sleep_summary:
        sleep_summary = sleep_data if isinstance(sleep_data, dict) else {}

    total_s = _safe(sleep_summary, "sleepTimeSeconds")
    deep_s = _safe(sleep_summary, "deepSleepSeconds")
    light_s = _safe(sleep_summary, "lightSleepSeconds")
    rem_s = _safe(sleep_summary, "remSleepSeconds")
    awake_s = _safe(sleep_summary, "awakeSleepSeconds")

    if total_s:
        sleep_score = _safe(sleep_summary, "sleepScores", "overall", "value") or _safe(
            sleep_summary, "sleepScore"
        )
        score_str = f"  score {sleep_score} (0-100)" if sleep_score is not None else ""
        print(f"\nSleep ({yesterday}): {_fmt_duration(total_s)}{score_str}")
        parts = []
        if deep_s:
            parts.append(f"deep {_fmt_duration(deep_s)}")
        if light_s:
            parts.append(f"light {_fmt_duration(light_s)}")
        if rem_s:
            parts.append(f"REM {_fmt_duration(rem_s)}")
        if awake_s:
            parts.append(f"awake {_fmt_duration(awake_s)}")
        if parts:
            print(f"  {' | '.join(parts)}")

    # Raw stats dump if requested
    if getattr(args, "raw", False):
        print("\n--- raw summary ---")
        print(json.dumps(summary, indent=2, default=str))
        print("\n--- raw stats ---")
        print(json.dumps(stats, indent=2, default=str))


def cmd_sleep(api: Garmin, args: Any) -> None:
    days = args.days
    print(f"=== Sleep: last {days} days ===\n")
    print(
        f"{'Date':<12} {'Total':>7} {'Deep':>7} {'Light':>7} {'REM':>7} {'Awake':>6} {'Score':>6}"
    )
    print("-" * 60)

    totals: list[int] = []
    deeps: list[int] = []
    lights: list[int] = []
    rems: list[int] = []
    awakes: list[int] = []
    scores: list[int] = []

    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        try:
            data = api.get_sleep_data(d)
        except Exception:
            print(f"{d:<12} error")
            continue

        dto = _safe(data, "dailySleepDTO") or data
        total = _safe(dto, "sleepTimeSeconds")
        deep = _safe(dto, "deepSleepSeconds")
        light = _safe(dto, "lightSleepSeconds")
        rem = _safe(dto, "remSleepSeconds")
        awake = _safe(dto, "awakeSleepSeconds")
        score = _safe(dto, "sleepScores", "overall", "value") or _safe(dto, "sleepScore")

        if total is None:
            print(f"{d:<12} no data")
            continue

        score_str = str(score) if score is not None else "-"
        print(
            f"{d:<12} {_fmt_duration(total):>7} {_fmt_duration(deep):>7}"
            f" {_fmt_duration(light):>7} {_fmt_duration(rem):>7}"
            f" {_fmt_duration(awake):>6} {score_str:>6}"
        )
        totals.append(total)
        if deep is not None:
            deeps.append(deep)
        if light is not None:
            lights.append(light)
        if rem is not None:
            rems.append(rem)
        if awake is not None:
            awakes.append(awake)
        if score is not None:
            scores.append(score)

    if totals:
        avg = lambda lst: int(sum(lst) / len(lst)) if lst else None  # noqa: E731
        score_avg = f"{int(sum(scores) / len(scores))}" if scores else "-"
        print("-" * 60)
        print(
            f"{'Avg':<12} {_fmt_duration(avg(totals)):>7} {_fmt_duration(avg(deeps)):>7}"
            f" {_fmt_duration(avg(lights)):>7} {_fmt_duration(avg(rems)):>7}"
            f" {_fmt_duration(avg(awakes)):>6} {score_avg:>6}"
        )

    if args.raw:
        last_date = date.today().isoformat()
        data = api.get_sleep_data(last_date)
        print("\n--- raw (last day) ---")
        print(json.dumps(data, indent=2, default=str))


def cmd_activities(api: Garmin, args: Any) -> None:
    raw_activities: list[Any] = list(api.get_activities(0, args.limit))

    # filter by recency if --days specified
    if args.days is not None:
        cutoff = (date.today() - timedelta(days=args.days)).isoformat()
        raw_activities = [
            a for a in raw_activities if (a.get("startTimeLocal") or "")[:10] >= cutoff
        ]

    if args.days is not None:
        print(f"=== Activities: last {args.days} days ({len(raw_activities)}) ===\n")
    else:
        print(f"=== Recent Activities ({len(raw_activities)}) ===\n")

    a: dict[str, Any]
    for a in raw_activities:
        adate = (a.get("startTimeLocal") or "")[:10]
        atype = a.get("activityType", {}).get("typeKey", a.get("activityName", "unknown"))
        name = a.get("activityName", "")
        duration_s = a.get("duration") or a.get("movingDuration")
        dist_m = a.get("distance")
        hr_avg = a.get("averageHR")
        hr_max = a.get("maxHR")
        calories = a.get("calories")
        elevation = a.get("elevationGain")

        # type-specific metrics
        pace_str = ""
        speed_str = ""
        if dist_m:
            if duration_s and atype in (
                "running",
                "trail_running",
                "treadmill_running",
                "walking",
                "hiking",
                "indoor_walking",
            ):
                pace_str = f"  {_fmt_pace(duration_s / dist_m)}"
            elif duration_s and atype in (
                "cycling",
                "road_biking",
                "mountain_biking",
                "virtual_ride",
            ):
                speed_kmh = (dist_m / 1000) / (duration_s / 3600)
                speed_str = f"  {speed_kmh:.1f} km/h"

        parts: list[str] = []
        if dist_m:
            parts.append(f"{dist_m / 1000:.2f} km")
        if duration_s:
            parts.append(_fmt_duration(duration_s))
        if pace_str:
            parts.append(pace_str.strip())
        if speed_str:
            parts.append(speed_str.strip())
        if hr_avg:
            hr_str = f"HR {_inum(hr_avg)}"
            if hr_max:
                hr_str += f"/{_inum(hr_max)}"
            parts.append(hr_str)
        if calories:
            parts.append(f"{_inum(calories)} kcal")
        if elevation:
            parts.append(f"+{elevation:.0f}m")

        label = _activity_label(atype, name)
        print(f"{adate}  {label:<30} {' | '.join(parts)}")

    if args.raw and raw_activities:
        print("\n--- raw (first activity) ---")
        print(json.dumps(raw_activities[0], indent=2, default=str))


def cmd_hrv(api: Garmin, args: Any) -> None:
    days = args.days
    print(f"=== HRV: last {days} days ===\n")
    print(
        f"{'Date':<12} {'Last night(ms)':>14} {'Weekly avg(ms)':>14} {'5-min high(ms)':>14} {'Baseline(ms)':>13} {'Status':<15}"
    )
    print("-" * 85)

    last_date_with_data = (date.today() - timedelta(days=1)).isoformat()
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        try:
            data = api.get_hrv_data(d)
        except Exception:
            print(f"{d:<12} error")
            continue

        s = _safe(data, "hrvSummary") or data
        if not s:
            print(f"{d:<12} no data")
            continue

        last_night = _safe(s, "lastNightAvg")
        weekly = _safe(s, "weeklyAvg")
        high5 = _safe(s, "lastNight5MinHigh")
        baseline_low = _safe(s, "baseline", "balancedLow")
        baseline_high = _safe(s, "baseline", "balancedUpper")
        status = _safe(s, "status") or "-"

        ln_str = str(last_night) if last_night is not None else "-"
        wk_str = str(weekly) if weekly is not None else "-"
        h5_str = str(high5) if high5 is not None else "-"
        baseline_str = f"{baseline_low}-{baseline_high}" if baseline_low else "-"

        print(f"{d:<12} {ln_str:>14} {wk_str:>14} {h5_str:>14} {baseline_str:>13} {status:<15}")
        if last_night is not None or weekly is not None:
            last_date_with_data = d

    if args.raw:
        data = api.get_hrv_data(last_date_with_data)
        print("\n--- raw ---")
        print(json.dumps(data, indent=2, default=str))


def cmd_weight(api: Garmin, args: Any) -> None:
    days = args.days
    end = date.today()
    start = end - timedelta(days=days - 1)

    try:
        data = api.get_weigh_ins(start.isoformat(), end.isoformat())
        entries: list[Any] = _safe(data, "dailyWeightSummaries") or []
    except Exception:
        entries = []

    # fallback: get_daily_weigh_ins returns a different shape
    if not entries:
        try:
            data = api.get_daily_weigh_ins(end.isoformat())
            entries = data if isinstance(data, list) else []
        except Exception:
            entries = []

    if not entries:
        print("no weight data")
        if args.raw:
            try:
                raw = api.get_weigh_ins(start.isoformat(), end.isoformat())
                print(json.dumps(raw, indent=2, default=str))
            except Exception as e:
                print(f"error: {e}")
        return

    print(f"=== Weight: {start} → {end} ===\n")
    print(f"{'Date':<12} {'Weight':>8} {'BMI':>6} {'Fat%':>6} {'Muscle%':>8} {'Bone(kg)':>9}")
    print("-" * 55)

    for entry in entries:
        # get_weigh_ins returns dailyWeightSummaries with nested allWeightMetrics
        d = _safe(entry, "summaryDate") or _safe(entry, "calendarDate") or "-"
        # try nested metrics first, then flat
        metrics = _safe(entry, "allWeightMetrics") or [entry]
        if isinstance(metrics, list) and metrics:
            m = metrics[-1]  # latest measurement of the day
        else:
            m = entry

        weight = _safe(m, "weight")
        if weight and weight > 1000:  # Garmin stores in grams
            weight = weight / 1000
        bmi = _safe(m, "bmi")
        fat_pct = _safe(m, "bodyFat")
        muscle_pct = _safe(m, "muscleMass")
        if muscle_pct and weight and muscle_pct > 100:
            muscle_pct = round(muscle_pct / (weight * 1000) * 100, 1)
        bone = _safe(m, "boneMass")
        if bone and bone > 100:
            bone = bone / 1000

        w_str = f"{weight:.1f} kg" if weight else "-"
        bmi_str = f"{bmi:.1f}" if bmi else "-"
        fat_str = f"{fat_pct:.1f}%" if fat_pct else "-"
        muscle_str = f"{muscle_pct:.1f}%" if muscle_pct else "-"
        bone_str = f"{bone:.2f}" if bone else "-"

        print(f"{d!s:<12} {w_str:>8} {bmi_str:>6} {fat_str:>6} {muscle_str:>8} {bone_str:>9}")

    if args.raw:
        raw = api.get_weigh_ins(start.isoformat(), end.isoformat())
        print("\n--- raw ---")
        print(json.dumps(raw, indent=2, default=str))


def cmd_spo2(api: Garmin, args: Any) -> None:
    days = args.days
    print(f"=== SpO2 / Respiration: last {days} days ===\n")
    print(f"{'Date':<12} {'SpO2 avg%':>10} {'SpO2 low%':>10} {'Resp(br/min)':>13} {'Resp low':>9}")
    print("-" * 58)

    last_date_with_data = (date.today() - timedelta(days=1)).isoformat()
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        try:
            resp_data = api.get_respiration_data(d)
        except Exception:
            resp_data = {}
        try:
            spo2_data = api.get_spo2_data(d)
        except Exception:
            spo2_data = {}

        # SpO2 lives in get_spo2_data; respiration rate in get_respiration_data
        spo2_avg = _safe(spo2_data, "averageSpO2") or _safe(spo2_data, "avgSleepSpO2")
        spo2_low = _safe(spo2_data, "lowestSpO2")
        resp_avg = _safe(resp_data, "avgWakingRespirationValue") or _safe(
            resp_data, "averageRespirationValue"
        )
        resp_low = _safe(resp_data, "lowestRespirationValue")

        if spo2_avg is None and resp_avg is None:
            print(f"{d:<12} no data")
            continue

        spo2_avg_str = f"{spo2_avg}%" if spo2_avg is not None else "-"
        spo2_low_str = f"{spo2_low}%" if spo2_low is not None else "-"
        resp_avg_str = f"{resp_avg:.1f}" if resp_avg is not None else "-"
        resp_low_str = f"{resp_low:.1f}" if resp_low is not None else "-"

        print(f"{d:<12} {spo2_avg_str:>10} {spo2_low_str:>10} {resp_avg_str:>13} {resp_low_str:>9}")
        last_date_with_data = d

    if args.raw:
        print("\n--- raw respiration ---")
        print(json.dumps(api.get_respiration_data(last_date_with_data), indent=2, default=str))
        print("\n--- raw spo2 ---")
        print(json.dumps(api.get_spo2_data(last_date_with_data), indent=2, default=str))


def _extract_sleep(data: Any) -> dict[str, Any]:
    """Extract sleep fields from get_sleep_data() response."""
    dto = _safe(data, "dailySleepDTO") or (_safe(data, "sleepTimeSeconds") and data) or {}
    if not isinstance(dto, dict):
        dto = {}
    return {
        "total_s": _safe(dto, "sleepTimeSeconds"),
        "deep_s": _safe(dto, "deepSleepSeconds"),
        "light_s": _safe(dto, "lightSleepSeconds"),
        "rem_s": _safe(dto, "remSleepSeconds"),
        "awake_s": _safe(dto, "awakeSleepSeconds"),
        "score": _safe(dto, "sleepScores", "overall", "value") or _safe(dto, "sleepScore"),
    }


def cmd_report(api: Garmin, args: Any) -> None:
    """Aggregated health report — all key metrics in one call."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    days = args.days

    # --- fetch ---
    summary = api.get_user_summary(today)
    try:
        hrv_raw = api.get_hrv_data(yesterday)
    except Exception:
        hrv_raw = {}
    try:
        spo2_raw = api.get_spo2_data(today)
    except Exception:
        spo2_raw = {}
    try:
        sleep_raw = api.get_sleep_data(yesterday)
    except Exception:
        sleep_raw = {}
    try:
        activities = list(api.get_activities(0, 1))
        last_act: dict[str, Any] = activities[0] if activities else {}
    except Exception:
        last_act = {}
    try:
        readiness_raw = api.get_training_readiness(today)
    except Exception:
        readiness_raw = {}
    try:
        t_status_raw = api.get_training_status(today)
    except Exception:
        t_status_raw = {}
    try:
        endurance_raw = api.get_endurance_score(today)
    except Exception:
        endurance_raw = {}

    sleep_trend: list[tuple[str, Any]] = []
    if days > 1:
        for i in range(days - 1, 0, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            try:
                sleep_trend.append((d, api.get_sleep_data(d)))
            except Exception:
                sleep_trend.append((d, {}))

    # --- extract ---
    steps = _safe(summary, "totalSteps")
    goal = _safe(summary, "dailyStepGoal") or 10000
    dist_m = _safe(summary, "totalDistanceMeters")
    calories = _safe(summary, "totalKilocalories")
    active_cal = _safe(summary, "activeKilocalories")
    rhr = _safe(summary, "restingHeartRate")
    hr_avg = _safe(summary, "averageHeartRate")
    hr_max = _safe(summary, "maxHeartRate")
    bb_current = _safe(summary, "bodyBatteryMostRecentValue")
    bb_high = _safe(summary, "bodyBatteryHighestValue")
    bb_low = _safe(summary, "bodyBatteryLowestValue")
    bb_charged = _safe(summary, "bodyBatteryChargedValue")
    bb_drained = _safe(summary, "bodyBatteryDrainedValue")
    stress_avg = _safe(summary, "averageStressLevel")

    hrv_s = _safe(hrv_raw, "hrvSummary") or hrv_raw
    hrv_last = _safe(hrv_s, "lastNightAvg")
    hrv_weekly = _safe(hrv_s, "weeklyAvg")
    hrv_status = _safe(hrv_s, "status")
    hrv_bl_low = _safe(hrv_s, "baseline", "balancedLow")
    hrv_bl_high = _safe(hrv_s, "baseline", "balancedUpper")

    spo2_avg = _safe(spo2_raw, "averageSpO2") or _safe(spo2_raw, "avgSleepSpO2")
    spo2_low = _safe(spo2_raw, "lowestSpO2")

    sl = _extract_sleep(sleep_raw)

    readiness_score = _safe(readiness_raw, "score") or _safe(
        readiness_raw, "trainingReadinessScore"
    )
    readiness_level = _safe(readiness_raw, "level") or _safe(
        readiness_raw, "trainingReadinessLevel"
    )
    t_status = _safe(t_status_raw, "mostRecentTrainingStatus") or _safe(
        t_status_raw, "trainingStatus"
    )
    endurance_score = _safe(endurance_raw, "overallScore")
    endurance_class = _ENDURANCE_CLASS.get(_safe(endurance_raw, "classification") or 0, "")

    # --- llm JSON output ---
    if args.llm:

        def _s(v: Any) -> Any:
            return None if v is None else (_inum(v) if isinstance(v, float) else v)

        stress_level = None
        if stress_avg is not None:
            stress_level = (
                "low"
                if stress_avg < 26
                else "medium"
                if stress_avg < 51
                else "high"
                if stress_avg < 76
                else "very high"
            )

        out: dict[str, Any] = {"date": today}
        if steps is not None:
            out["steps"] = _s(steps)
            out["steps_goal"] = _s(goal)
        if dist_m is not None:
            out["distance_km"] = round(dist_m / 1000, 1)
        if calories is not None:
            out["calories_kcal"] = _s(calories)
        if active_cal is not None:
            out["active_calories_kcal"] = _s(active_cal)
        if rhr is not None:
            out["hr_resting_bpm"] = _s(rhr)
        if hr_avg is not None:
            out["hr_avg_bpm"] = _s(hr_avg)
        if hr_max is not None:
            out["hr_max_bpm"] = _s(hr_max)
        if bb_current is not None:
            out["body_battery_current"] = _s(bb_current)
        if bb_high is not None:
            out["body_battery_peak"] = _s(bb_high)
        if bb_low is not None:
            out["body_battery_low"] = _s(bb_low)
        if bb_charged:
            out["body_battery_charged"] = _s(bb_charged)
        if bb_drained:
            out["body_battery_drained"] = _s(bb_drained)
        if stress_avg is not None:
            out["stress_avg"] = _s(stress_avg)
            out["stress_level"] = stress_level
        if spo2_avg is not None:
            out["spo2_avg_pct"] = _s(spo2_avg)
        if spo2_low is not None:
            out["spo2_low_pct"] = _s(spo2_low)
        if readiness_score is not None:
            out["training_readiness_score"] = _s(readiness_score)
        if readiness_level:
            out["training_readiness_level"] = readiness_level
        if t_status:
            out["training_status"] = t_status
        if endurance_score is not None:
            out["endurance_score"] = _s(endurance_score)
        if endurance_class:
            out["endurance_class"] = endurance_class
        out["sleep_date"] = yesterday
        if sl["total_s"] is not None:
            out["sleep_total_min"] = int(sl["total_s"]) // 60
        if sl["deep_s"] is not None:
            out["sleep_deep_min"] = int(sl["deep_s"]) // 60
        if sl["light_s"] is not None:
            out["sleep_light_min"] = int(sl["light_s"]) // 60
        if sl["rem_s"] is not None:
            out["sleep_rem_min"] = int(sl["rem_s"]) // 60
        if sl["awake_s"] is not None:
            out["sleep_awake_min"] = int(sl["awake_s"]) // 60
        if sl["score"] is not None:
            out["sleep_score"] = _s(sl["score"])
        if hrv_last is not None:
            out["hrv_last_night_ms"] = _s(hrv_last)
        if hrv_weekly is not None:
            out["hrv_weekly_avg_ms"] = _s(hrv_weekly)
        if hrv_bl_low is not None:
            out["hrv_baseline_low_ms"] = _s(hrv_bl_low)
        if hrv_bl_high is not None:
            out["hrv_baseline_high_ms"] = _s(hrv_bl_high)
        if hrv_status:
            out["hrv_status"] = hrv_status
        if last_act:
            out["last_activity_date"] = (last_act.get("startTimeLocal") or "")[:10]
            out["last_activity_type"] = last_act.get("activityType", {}).get(
                "typeKey"
            ) or last_act.get("activityName")
            act_dist = last_act.get("distance")
            if act_dist:
                out["last_activity_distance_km"] = round(act_dist / 1000, 1)
            act_dur = last_act.get("duration") or last_act.get("movingDuration")
            if act_dur:
                out["last_activity_duration_min"] = int(act_dur) // 60
            if act_dist and act_dur:
                out["last_activity_pace"] = _fmt_pace(act_dur / act_dist)
            act_hr = last_act.get("averageHR")
            if act_hr:
                out["last_activity_hr_avg"] = _s(act_hr)
        if sleep_trend:
            trend = []
            for d, raw in sleep_trend:
                s = _extract_sleep(raw)
                if s["total_s"] is not None:
                    trend.append(
                        {
                            "date": d,
                            "total_min": int(s["total_s"]) // 60,
                            "deep_min": int(s["deep_s"]) // 60 if s["deep_s"] is not None else None,
                            "rem_min": int(s["rem_s"]) // 60 if s["rem_s"] is not None else None,
                            "score": _s(s["score"]),
                        }
                    )
            if trend:
                out["sleep_trend"] = trend

        print(json.dumps(out))
        return

    # --- text output ---
    print(f"=== Health Report: {today} ===\n")

    # Today
    print("TODAY")
    if steps is not None:
        pct = int(steps / goal * 100) if goal else 0
        parts = [f"Steps {_inum(steps):,}/{_inum(goal):,} ({pct}%)"]
        if dist_m is not None:
            parts.append(f"{dist_m / 1000:.1f}km")
        if calories is not None:
            cal_str = f"{_inum(calories)} kcal"
            if active_cal:
                cal_str += f" ({_inum(active_cal)} active)"
            parts.append(cal_str)
        print("  " + " | ".join(parts))

    hr_parts = []
    if rhr:
        hr_parts.append(f"resting {_inum(rhr)}")
    if hr_avg and not isinstance(hr_avg, list):
        hr_parts.append(f"avg {_inum(hr_avg)}")
    if hr_max:
        hr_parts.append(f"max {_inum(hr_max)}")
    if hr_parts:
        print(f"  HR: {' | '.join(hr_parts)} bpm")

    bb_parts = []
    if bb_current is not None:
        bb_parts.append(f"current {_inum(bb_current)}")
    if bb_high is not None:
        bb_parts.append(f"peak {_inum(bb_high)}")
    if bb_low is not None:
        bb_parts.append(f"low {_inum(bb_low)}")
    if bb_charged or bb_drained:
        delta = []
        if bb_charged:
            delta.append(f"+{_inum(bb_charged)}")
        if bb_drained:
            delta.append(f"-{_inum(bb_drained)}")
        bb_parts.append(f"({'/ '.join(delta)})")
    if bb_parts:
        print(f"  Body Battery (0-100): {' | '.join(bb_parts)}")

    misc = []
    if stress_avg is not None:
        level = (
            "low"
            if stress_avg < 26
            else "medium"
            if stress_avg < 51
            else "high"
            if stress_avg < 76
            else "very high"
        )
        misc.append(f"Stress {_inum(stress_avg)} ({level})")
    if spo2_avg is not None:
        s = f"SpO2 {_inum(spo2_avg)}%"
        if spo2_low:
            s += f" low {_inum(spo2_low)}%"
        misc.append(s)
    if misc:
        print("  " + " | ".join(misc))

    if readiness_score is not None or t_status or endurance_score is not None:
        r_parts = []
        if readiness_score is not None:
            lvl = f" ({readiness_level})" if readiness_level else ""
            r_parts.append(f"Readiness {_inum(readiness_score)}/100{lvl}")
        if t_status:
            r_parts.append(f"Status {t_status}")
        if endurance_score is not None:
            cls_str = f" ({endurance_class})" if endurance_class else ""
            r_parts.append(f"Endurance {_inum(endurance_score)}{cls_str}")
        print(f"  Training: {' | '.join(r_parts)}")

    # Sleep
    if sl["total_s"]:
        sc_str = f"  score {_inum(sl['score'])} (0-100)" if sl["score"] is not None else ""
        print(f"\nSLEEP {yesterday} — {_fmt_duration(sl['total_s'])}{sc_str}")
        sl_parts = []
        if sl["deep_s"]:
            sl_parts.append(f"Deep {_fmt_duration(sl['deep_s'])}")
        if sl["rem_s"]:
            sl_parts.append(f"REM {_fmt_duration(sl['rem_s'])}")
        if sl["light_s"]:
            sl_parts.append(f"Light {_fmt_duration(sl['light_s'])}")
        if sl["awake_s"]:
            sl_parts.append(f"Awake {_fmt_duration(sl['awake_s'])}")
        if sl_parts:
            print(f"  {' | '.join(sl_parts)}")

    # HRV
    hrv_parts = []
    if hrv_last is not None:
        hrv_parts.append(f"last night {hrv_last}ms")
    if hrv_weekly is not None:
        hrv_parts.append(f"weekly avg {hrv_weekly}ms")
    if hrv_bl_low and hrv_bl_high:
        hrv_parts.append(f"baseline {hrv_bl_low}-{hrv_bl_high}ms")
    if hrv_status:
        hrv_parts.append(f"status {hrv_status}")
    if hrv_parts:
        print(f"\nHRV  {' | '.join(hrv_parts)}")

    # Last activity
    if last_act:
        adate = (last_act.get("startTimeLocal") or "")[:10]
        atype = last_act.get("activityType", {}).get("typeKey") or "unknown"
        aname = last_act.get("activityName", "")
        act_dist = last_act.get("distance")
        act_dur = last_act.get("duration") or last_act.get("movingDuration")
        act_hr = last_act.get("averageHR")
        act_parts = []
        if act_dist:
            act_parts.append(f"{act_dist / 1000:.1f}km")
        if act_dur:
            act_parts.append(_fmt_duration(act_dur))
        if act_dist and act_dur:
            act_parts.append(_fmt_pace(act_dur / act_dist))
        if act_hr:
            act_parts.append(f"HR {_inum(act_hr)}")
        label = _activity_label(atype, aname)
        print(f"\nLAST ACTIVITY\n  {adate}  {label}  {' | '.join(act_parts)}")

    # Sleep trend
    if sleep_trend:
        print(f"\nSLEEP TREND {days - 1}d  date / total / deep / REM / score")
        for d, raw in sleep_trend:
            s = _extract_sleep(raw)
            if s["total_s"] is None:
                print(f"  {d}: no data")
                continue
            sc = str(_inum(s["score"])) if s["score"] is not None else "-"
            print(
                f"  {d}: {_fmt_duration(s['total_s'])} / "
                f"{_fmt_duration(s['deep_s'])} / "
                f"{_fmt_duration(s['rem_s'])} / {sc}"
            )


def cmd_activity(api: Garmin, args: Any) -> None:
    """Drill-down for a single activity: HR zones, laps, stress."""
    activity_id = args.activity_id

    try:
        detail = api.get_activity(activity_id)
    except Exception as e:
        sys.exit(f"error fetching activity {activity_id}: {e}")

    if args.raw:
        print(json.dumps(detail, indent=2, default=str))
        return

    # Basic info
    name = _safe(detail, "activityName") or "unknown"
    atype = _safe(detail, "activityTypeDTO", "typeKey") or ""
    start = (_safe(detail, "summaryDTO", "startTimeLocal") or "")[:16]
    print(f"=== Activity: {name} ===")
    if atype:
        print(f"Type:   {atype}")
    if start:
        print(f"Date:   {start}")

    # Summary metrics
    s = _safe(detail, "summaryDTO") or {}
    dur = _safe(s, "duration") or _safe(s, "movingDuration")
    dist = _safe(s, "distance")
    hr_avg = _safe(s, "averageHR")
    hr_max = _safe(s, "maxHR")
    calories = _safe(s, "calories")
    elev = _safe(s, "elevationGain")
    if dur:
        print(f"Duration: {_fmt_duration(dur)}")
    if dist:
        pace_str = f"  ({_fmt_pace(dur / dist)})" if dur else ""
        print(f"Distance: {dist / 1000:.2f} km{pace_str}")
    if hr_avg is not None:
        hr_str = f"avg {_inum(hr_avg)}"
        if hr_max:
            hr_str += f" | max {_inum(hr_max)}"
        print(f"HR:       {hr_str} bpm")
    if calories:
        print(f"Calories: {_inum(calories)} kcal")
    if elev:
        print(f"Elevation: +{elev:.0f} m")

    # HR zones
    try:
        zones_raw = api.get_activity_hr_in_timezones(activity_id)
    except Exception:
        zones_raw = []

    if zones_raw:
        total_secs = sum(_safe(z, "secsInZone") or 0 for z in zones_raw)
        print("\nHR Zones:")
        for z in zones_raw:
            zname = _safe(z, "zoneName") or _safe(z, "zoneNumber") or "?"
            secs = _safe(z, "secsInZone") or 0
            pct = secs / total_secs * 100 if total_secs else 0
            print(f"  Zone {zname}: {_fmt_duration(secs)}  ({pct:.0f}%)")

    # Laps
    try:
        laps_raw = api.get_activity_splits(activity_id)
        laps: list[Any] = (
            _safe(laps_raw, "lapDTOs")
            or _safe(laps_raw, "items")
            or (laps_raw if isinstance(laps_raw, list) else [])
        )
    except Exception:
        laps = []

    valid_laps = [
        lap
        for lap in laps
        if (_safe(lap, "distance") or 0) >= 10 and (_safe(lap, "duration") or 0) >= 30
    ]
    if valid_laps:
        print(f"\nLaps ({len(valid_laps)}):")
        for i, lap in enumerate(valid_laps, 1):
            ldur = _safe(lap, "duration")
            ldist = _safe(lap, "distance")
            lhr = _safe(lap, "averageHR")
            lparts = []
            if ldist:
                lparts.append(f"{ldist / 1000:.2f} km")
            if ldur:
                lparts.append(_fmt_duration(ldur))
            if ldist and ldur:
                lparts.append(_fmt_pace(ldur / ldist))
            if lhr:
                lparts.append(f"HR {_inum(lhr)}")
            print(f"  {i:>3}.  {' | '.join(lparts)}")


def cmd_steps(api: Garmin, args: Any) -> None:
    """Step totals aggregated by day, week, or month."""
    today = date.today()
    end = today
    start = end - timedelta(days=args.days - 1)

    try:
        data = api.get_daily_steps(start.isoformat(), end.isoformat())
        if not isinstance(data, list):
            data = []
    except Exception as e:
        sys.exit(f"error fetching steps: {e}")

    if args.raw:
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("no step data")
        return

    period = args.period
    print(f"=== Steps: {start} → {end} ===\n")

    if period == "day":
        print(f"{'Date':<12} {'Steps':>8} {'Goal':>8} {'%':>5} {'Distance':>10}")
        print("-" * 47)
        for row in data:
            d = _safe(row, "calendarDate") or "-"
            steps = _safe(row, "totalSteps") or 0
            goal = _safe(row, "stepGoal") or 10000
            dist_m = _safe(row, "totalDistance")
            pct = int(steps / goal * 100) if goal else 0
            dist_str = f"{dist_m / 1000:.1f} km" if dist_m else "-"
            print(f"{d!s:<12} {steps:>8,} {goal:>8,} {pct:>4}% {dist_str:>10}")

        total = sum(_safe(r, "totalSteps") or 0 for r in data)
        valid = [r for r in data if (_safe(r, "totalSteps") or 0) > 0]
        if valid:
            avg = total // len(valid)
            print("-" * 47)
            print(f"{'Total':<12} {total:>8,}   {'Avg':>8} {'':>5} {avg:>10,}")

    elif period == "week":
        # Group by ISO week
        from collections import defaultdict

        weeks: dict[str, list[int]] = defaultdict(list)
        for row in data:
            d_str = str(_safe(row, "calendarDate") or "")
            if not d_str:
                continue
            d_obj = date.fromisoformat(d_str)
            week_key = f"{d_obj.isocalendar().year}-W{d_obj.isocalendar().week:02d}"
            steps = _safe(row, "totalSteps") or 0
            weeks[week_key].append(steps)

        today_iso = today
        current_week = f"{today_iso.isocalendar().year}-W{today_iso.isocalendar().week:02d}"
        print(f"{'Week':<14} {'Total':>9} {'Daily avg':>10}")
        print("-" * 36)
        for week, step_list in sorted(weeks.items()):
            total = sum(step_list)
            avg = total // len(step_list) if step_list else 0
            label = f"{week}*" if week == current_week else week
            print(f"{label:<14} {total:>9,} {avg:>10,}")

    elif period == "month":
        from collections import defaultdict

        months: dict[str, list[int]] = defaultdict(list)
        for row in data:
            d_str = str(_safe(row, "calendarDate") or "")
            if not d_str:
                continue
            month_key = d_str[:7]  # YYYY-MM
            steps = _safe(row, "totalSteps") or 0
            months[month_key].append(steps)

        current_month = today.strftime("%Y-%m")
        print(f"{'Month':<12} {'Total':>9} {'Daily avg':>10} {'Days':>5}")
        print("-" * 39)
        for month, step_list in sorted(months.items()):
            total = sum(step_list)
            avg = total // len(step_list) if step_list else 0
            label = f"{month}*" if month == current_month else month
            print(f"{label:<12} {total:>9,} {avg:>10,} {len(step_list):>5}")


def cmd_stats(api: Garmin, args: Any) -> None:
    """Dump all available raw stats for today."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    fetchers: list[tuple[str, Any]] = [
        ("user_summary", lambda: api.get_user_summary(today)),
        ("stats", lambda: api.get_stats(today)),
        ("heart_rates", lambda: api.get_heart_rates(today)),
        ("hrv", lambda: api.get_hrv_data(today)),
        ("stress", lambda: api.get_stress_data(today)),
        ("body_battery", lambda: api.get_body_battery(today, today)),
        ("respiration", lambda: api.get_respiration_data(today)),
        ("sleep", lambda: api.get_sleep_data(yesterday)),
        ("activities_today", lambda: api.get_activities_fordate(today)),
        ("activities_recent", lambda: api.get_activities(0, 5)),
        ("personal_info", lambda: api.get_user_profile()),
        ("body_composition", lambda: api.get_body_composition(today)),
        (
            "weigh_ins",
            lambda: api.get_weigh_ins((date.today() - timedelta(days=30)).isoformat(), today),
        ),
        ("endurance_score", lambda: api.get_endurance_score(today)),
    ]

    results: dict[str, Any] = {}
    for name, fn in fetchers:
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = f"error: {e}"

    print(json.dumps(results, indent=2, default=str))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="garq",
        description="Garmin Connect stats fetcher",
    )
    # shared --raw flag available on every subcommand (both positions work)
    raw_parent = argparse.ArgumentParser(add_help=False)
    raw_parent.add_argument("--raw", action="store_true", help="dump raw API response as JSON")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "today",
        parents=[raw_parent],
        help="full daily summary (steps, HR, sleep, body battery, stress, HRV)",
    )

    p_sleep = sub.add_parser("sleep", parents=[raw_parent], help="sleep data for the last N days")
    p_sleep.add_argument("--days", type=int, default=7, metavar="N")

    p_act = sub.add_parser("activities", parents=[raw_parent], help="recent activities")
    p_act.add_argument("--limit", type=int, default=10, metavar="N")
    p_act.add_argument("--days", type=int, default=None, metavar="N", help="filter by last N days")

    p_hrv = sub.add_parser("hrv", parents=[raw_parent], help="HRV trend")
    p_hrv.add_argument("--days", type=int, default=7, metavar="N")

    p_weight = sub.add_parser(
        "weight", parents=[raw_parent], help="weight / body composition history"
    )
    p_weight.add_argument("--days", type=int, default=30, metavar="N")

    p_spo2 = sub.add_parser("spo2", parents=[raw_parent], help="SpO2 and respiration trend")
    p_spo2.add_argument("--days", type=int, default=7, metavar="N")

    p_report = sub.add_parser(
        "report",
        parents=[raw_parent],
        help="aggregated health report (all key metrics in one call)",
    )
    p_report.add_argument(
        "--days", type=int, default=1, metavar="N", help="include sleep trend for last N days"
    )
    p_report.add_argument("--llm", action="store_true", help="output flat JSON optimized for LLM")

    p_activity = sub.add_parser(
        "activity", parents=[raw_parent], help="drill-down for a single activity (HR zones, laps)"
    )
    p_activity.add_argument("activity_id", type=int, help="activity ID (from activities --raw)")

    p_steps = sub.add_parser("steps", parents=[raw_parent], help="step totals by day/week/month")
    p_steps.add_argument("--days", type=int, default=30, metavar="N")
    p_steps.add_argument(
        "--period",
        choices=["day", "week", "month"],
        default="day",
        help="aggregation period (default: day)",
    )

    sub.add_parser("stats", parents=[raw_parent], help="dump all raw stats as JSON")

    args = parser.parse_args()

    try:
        api = _load_api()
    except KeyboardInterrupt:
        sys.exit(1)

    dispatch = {
        "today": cmd_today,
        "sleep": cmd_sleep,
        "activities": cmd_activities,
        "activity": cmd_activity,
        "hrv": cmd_hrv,
        "weight": cmd_weight,
        "spo2": cmd_spo2,
        "steps": cmd_steps,
        "report": cmd_report,
        "stats": cmd_stats,
    }
    dispatch[args.cmd](api, args)


if __name__ == "__main__":
    main()
