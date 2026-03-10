# garq

Garmin Connect stats fetcher for personal use. Single-file Python script,
runs via [uv](https://github.com/astral-sh/uv), designed as a
[Claude Code](https://claude.ai/claude-code) skill.

## Requirements

- [uv](https://github.com/astral-sh/uv)
- Garmin Connect account
- macOS keychain (or any keyring backend supported by the
  [keyring](https://github.com/jaraco/keyring) library)

## Setup

```zsh
git clone https://github.com/rmrfus/garq ~/Projects/garq
chmod +x ~/Projects/garq/garq.py

# first run — prompts for email/password, stores in keychain
~/Projects/garq/garq.py today
```

Credentials are stored in the system keychain under service `garq`.
OAuth2 tokens are cached in `~/.garth`. Subsequent runs are silent.
MFA is supported (prompts when required).

## Commands

```
report      all key metrics in one call (preferred entry point)
today       full daily summary: steps, HR, HRV, body battery, stress, sleep
sleep       sleep table for last N days
activities  recent activities list
activity    single activity drill-down: HR zones + lap splits
hrv         HRV trend table
weight      weight / body composition history
spo2        SpO2 and respiration trend
steps       step totals by day / week / month
stats       dump all raw JSON for today (debugging)
```

### Examples

```zsh
# all key metrics, flat JSON — ideal for piping to an LLM
./garq.py report --llm

# include 7-day sleep trend in report
./garq.py report --days 7

# full daily summary (human-readable)
./garq.py today

# sleep history
./garq.py sleep --days 14

# recent activities
./garq.py activities --limit 20
./garq.py activities --days 7

# activity drill-down (get ID from `activities --raw`)
./garq.py activity 12345678

# HRV trend
./garq.py hrv --days 14

# weight history
./garq.py weight --days 90

# SpO2 + respiration
./garq.py spo2 --days 14

# step aggregation
./garq.py steps
./garq.py steps --days 90 --period week
./garq.py steps --days 365 --period month

# raw API response (any command)
./garq.py today --raw
./garq.py hrv --days 7 --raw
```

### `report --llm` output

Flat JSON with no nulls, no arrays, no nested dicts — designed for LLM consumption:

```json
{
  "date": "2026-03-10",
  "steps": 8432,
  "steps_goal": 10000,
  "distance_km": 6.7,
  "hr_resting_bpm": 58,
  "body_battery_current": 45,
  "stress_avg": 24,
  "stress_level": "low",
  "spo2_avg_pct": 96,
  "sleep_date": "2026-03-09",
  "sleep_total_min": 452,
  "sleep_deep_min": 105,
  "sleep_score": 78,
  "hrv_last_night_ms": 48,
  "hrv_weekly_avg_ms": 52,
  "hrv_status": "BALANCED"
}
```

## Claude Code skill

Copy `SKILL.md` to `~/.claude/skills/garq/SKILL.md`. Claude will then
automatically invoke `garq.py` when asked about health data, steps, sleep,
HRV, activities, etc.

```zsh
mkdir -p ~/.claude/skills/garq
cp SKILL.md ~/.claude/skills/garq/SKILL.md
```

## Dev

```zsh
# run checks (ruff + ty + pytest)
uv run ruff check garq.py
uv run ruff format garq.py
uv run ty check garq.py
uv run pytest test_garq.py -v
```

Tests use mocked API — no real credentials needed. ~0.2s to run.
