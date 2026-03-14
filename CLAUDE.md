# garq

Garmin Connect stats fetcher. Single-file Python script, invoked as a Claude skill.

## Structure

```
garq.py               # the script — UV shebang, inline deps, all logic here
pyproject.toml        # dev tooling only (ruff, ty, pytest); runtime deps mirrored for type checking
test_garq.py          # unit tests — mocked API, no real credentials needed
test_claude_skill.py  # end-to-end skill tester — runs questions through `claude -p`
SKILL.md              # skill definition — deploy to ~/.claude/skills/garq/

~/.claude/skills/garq/garq.py   # deployed script (copy from repo)
~/.claude/skills/garq/SKILL.md  # deployed skill definition (copy from repo)
```

## Running

```zsh
./garq.py today
./garq.py sleep --days 14
./garq.py activities --limit 20
./garq.py activity 12345678      # drill-down: HR zones + laps (ID from activities --raw)
./garq.py hrv --days 7
./garq.py weight --days 30
./garq.py steps --days 90 --period week
./garq.py steps --period month
./garq.py stats          # full raw JSON dump
# --raw flag available on all commands
```

## Dev checks (always run before finishing)

```zsh
uv run ruff check garq.py
uv run ruff format garq.py
uv run ty check garq.py
uv run pytest test_garq.py -v
```

All four must pass. Tests run in ~0.2s, no network needed.

## Testing

```zsh
# unit tests (mocked API, fast)
uv run pytest test_garq.py -v

# end-to-end skill test (requires real auth + claude CLI)
./test_claude_skill.py
./test_claude_skill.py --out results.md   # save report
./test_claude_skill.py --fast             # skip final analysis pass
```

When adding a new subcommand, add unit tests to `test_garq.py`:
- formatter/helper functions → test as pure functions
- `cmd_*` functions → mock the API with `MagicMock`, assert on `capsys.readouterr().out`
- cover: happy path, no data, API error (graceful degradation)

## Auth

- Tokens cached in `~/.garth` (garth OAuth2)
- Credentials (email/password) in system keychain under service `garq`
- First run is interactive; subsequent runs are silent
- MFA supported via `prompt_mfa` callback
- On login failure: keychain creds are deleted so user can re-enter next run

## Adding a new subcommand

1. Add `cmd_<name>(api, args)` function
2. Add parser in `main()` under `sub.add_parser(...)`
3. Add to `dispatch` dict
4. **Always update `SKILL.md` in the repo** and re-deploy: argument-hint, Commands block, Workflow section

## IMPORTANT: keep the skill in sync

Any change to garq.py that affects user-facing functionality **must** be reflected in
`SKILL.md` and both files re-deployed to `~/.claude/skills/garq/` before the task is considered done:

- New subcommand → add to argument-hint, Commands block, Workflow
- New flag → update argument-hint and relevant command example
- Changed default (--days, --limit, etc.) → update the example in Commands
- Removed/renamed command → remove from all three places
- Changed trigger scenarios → update the `description` field in the frontmatter

After any change: `cp garq.py SKILL.md ~/.claude/skills/garq/`

## garminconnect API notes

- Dates: always `YYYY-MM-DD` strings
- Some endpoints store weight/bone in grams — divide by 1000
- `get_daily_weigh_ins(cdate)` takes a single date, not a range
- `get_weigh_ins(start, end)` returns `dailyWeightSummaries` list
- Wrap all API calls in try/except — endpoints silently fail or return empty on missing data
- Use `--raw` / `args.raw` + `json.dumps` to inspect actual response shape when adding new endpoints
