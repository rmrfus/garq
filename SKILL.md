---
name: garq
description: Fetch Garmin Connect health stats. Trigger when user asks about their Garmin data, steps, heart rate, HRV, sleep, body battery, stress, activities, weight, body composition, SpO2, or respiration — "покажи гармин", "как я спал", "сколько шагов", "покажи активности", "HRV сегодня", "body battery", "что там гармин говорит", "покажи вес", "динамика веса", "SpO2", "кислород во сне".
argument-hint: "[report|today|sleep|activities|activity|hrv|weight|spo2|steps|stats] [--days N] [--limit N] [--period day|week|month] [--raw] [--llm]"
allowed-tools: Bash
---

Use `${CLAUDE_SKILL_DIR}/garq.py` to fetch Garmin Connect data.

The script uses a `uv` shebang — run it directly, not with `python`. Tokens are cached in `~/.garth`; credentials in system keychain. First run is interactive.

## Commands

```bash
# ALL KEY METRICS IN ONE CALL (preferred for LLM use)
${CLAUDE_SKILL_DIR}/garq.py report              # compact text
${CLAUDE_SKILL_DIR}/garq.py report --llm        # flat JSON, no nulls, no arrays
${CLAUDE_SKILL_DIR}/garq.py report --days 7     # include 7-day sleep trend
${CLAUDE_SKILL_DIR}/garq.py report --days 7 --llm

# Full daily summary: steps, HR, HRV, body battery, stress, sleep
${CLAUDE_SKILL_DIR}/garq.py today

# Sleep for last N days (default 7)
${CLAUDE_SKILL_DIR}/garq.py sleep --days 14

# Recent activities (default 10); --days filters by recency
${CLAUDE_SKILL_DIR}/garq.py activities --limit 20
${CLAUDE_SKILL_DIR}/garq.py activities --days 7

# HRV trend for last N days (default 7)
${CLAUDE_SKILL_DIR}/garq.py hrv --days 14

# Weight / body composition history (default 30 days)
${CLAUDE_SKILL_DIR}/garq.py weight --days 90

# SpO2 and respiration trend (default 7 days)
${CLAUDE_SKILL_DIR}/garq.py spo2 --days 14

# Single activity drill-down: HR zones, laps, pace (ID from `activities --raw`)
${CLAUDE_SKILL_DIR}/garq.py activity 12345678

# Step totals by day / week / month (default 30 days, daily)
${CLAUDE_SKILL_DIR}/garq.py steps
${CLAUDE_SKILL_DIR}/garq.py steps --days 90 --period week
${CLAUDE_SKILL_DIR}/garq.py steps --days 365 --period month

# Dump all raw JSON stats for today
${CLAUDE_SKILL_DIR}/garq.py stats
```

`--raw` can be placed after the subcommand: `garq.py today --raw`, `garq.py hrv --days 14 --raw`.

## "no data" semantics

- `today` shows **yesterday's** sleep — Garmin associates sleep with the wake-up date
- `no data` on sleep/HRV for today's date is **normal** before sync or before tonight's sleep
- Sleep for the current night appears the **next morning** after watch syncs
- If recent dates all show `no data`, the watch hasn't synced — check with `sleep --days 3`
- HRV `no data` for today is expected; use `hrv --days 7` to see recent trend

## Workflow

- User asks about health in general → `report --llm` (all key metrics, one call)
- User asks about today's health → `report` or `today`
- User asks about sleep → `sleep`
- User asks about workouts/runs/rides → `activities`
- User asks about a specific workout details (zones, laps) → `activity <id>` (get ID from `activities --raw`)
- User asks about step count trend / weekly steps / monthly steps → `steps --period week` or `steps --period month`
- User asks about HRV/recovery → `hrv`
- User asks about weight, body fat, body composition → `weight`
- User asks about SpO2, blood oxygen, breathing rate, respiration → `spo2`
- User asks "what does Garmin say" / broad data request → `today` then `stats` if needed
- If a command fails with auth error, tell the user to run `garq.py today` manually in terminal to re-authenticate

## Output format

Commands print human-readable text. Use `--raw` when you need specific fields not shown in the default output. `stats` always dumps full JSON.

## Notes on specific commands

- `today` — body battery shows `current | peak | low | +charged | -drained`; sleep includes score
- `hrv` — columns: Last night(ms), Weekly avg(ms), 5-min high(ms), Baseline(ms), Status
- `spo2` — columns: SpO2 avg%, SpO2 low%, Resp(br/min), Resp low; uses two API calls internally
- `sleep` — includes Avg row at the bottom of the table
- `activity <id>` — shows HR zones and lap splits; activity IDs visible in `activities --raw`
- `steps` — `--period day` (default) shows per-day table with totals; `week`/`month` aggregate by ISO week or calendar month
