# Command Center

Plain-English control for the website. You type one word; the machine does the
real Git/GitHub work. No browser, no code, no terminal beyond the command.

> **Status: Phase 0** — the skeleton plus the read-only `status` command. The
> other verbs print a friendly "coming in a later phase" message for now. See the
> build prompt (`Command Center Engine — Claude Code Build Prompt`) for the plan.

## The commands (the plan)
| Command | What it does | Phase |
|---|---|---|
| `status` | Show what's happening: running/paused, what's waiting on you, last publish, live-site check. | **0 (built)** |
| `run "…"` | Start a change — hand a plain-English task to the builder. | 1 |
| `preview` | See the pending change on a private test link before it's live. | 1 |
| `hold` | Park the pending change; don't publish. | 1 |
| `stop` | Pause everything now (instant). | 2 |
| `resume` | Un-pause. | 2 |
| `ship` | Publish the pending change to the live site. | 3 |
| `undo` | Roll the site back to the last known-good version. | 3 |

## Run it
```
python3 cc.py status
python3 cc.py help
```
Config: built-in defaults, override with a TOML file via `CC_CONFIG=/path/to/cc.toml`
(copy `config.example.toml`) or with `CC_*` environment variables.

## How it's built to be safe (the rules baked in)
- **Only `ship`/`undo` can publish**, and only with a separate owner merge key kept
  away from the build worker. `status/run/preview/hold/stop/resume` need no key.
- **The build worker can never merge** — the human-merge gate is enforced by GitHub
  (branch protection + a separate robot identity). This engine sits on top of it.
- **No cloud credentials, ever** — publishing is the site's own deploy pipeline;
  `ship`/`undo` confirm a deploy went live via GitHub + an HTTP check, not by holding
  Azure keys.
- **Write-ahead, append-only command log** (`ccengine/log.py`) + a **single-flight
  lock** (`ccengine/lock.py`) so a crash is recoverable and two commands can't race.
- **No network listener** in this CLI — your machine login is the auth.

## Layout
```
cc.py                  # the CLI (a thin face over the core, so a UI can wrap it later)
ccengine/config.py     # config (defaults / TOML / env). No secrets.
ccengine/ui.py         # friendly, jargon-free output; never raw git/gh errors
ccengine/log.py        # write-ahead, append-only command log
ccengine/lock.py       # single-flight lock (records holder PID for a future stop)
ccengine/provider.py   # the ONLY place that talks to gh / the live site (mockable)
ccengine/status.py     # the status command
tests/                 # unit tests (run: python3 -m unittest discover -s tests -t .)
```
