# AI Brain Loop — Timer Setup (Level 2 automation)

Turns the manual launch line into an automatic alarm clock. Schedule (Reny, 2026-07-14):
**always-on, every 2 minutes.** Uses **Windows Task Scheduler** (reliable on WSL2, and Reny's home turf)
to run the guard script `scripts/webcat-loop.sh` as the caged `webcat-worker` user.

## Why the guard script (not raw `claude`) — cheap when idle
Each tick runs `webcat-loop.sh`, which does only a `git fetch` + a couple of `grep`s. It wakes Claude
(costs tokens) ONLY when it finds a genuinely new approved task and no STOP flag. So a 2-minute cadence
is a *speed* dial (how fast an approved task starts), not a cost dial — empty ticks are ~free.

## Safety belts baked into the guard (from the council-reviewed design)
- **Single-flight lock** — a new tick exits if a run is already going (no overlap/stacking).
- **STOP flag** — create `handoff/STOP` (a PR, or the GitHub "Add file" button) → loop halts every tick.
- **Placeholder skip** — idle mailbox = nothing happens.
- **Per-task dedupe** — a task runs once; it won't re-run until you approve a *different* task.
- **Daily cap** — max 20 runs/day; a runaway can't burn the plan overnight.
- **Wall-clock timeout (15m) + turn cap (25)** on every Claude run.

## Install — Part A (in Ubuntu, as webcat-worker) — make the script live + smoke-test
    su - webcat-worker          # if not already
    cd ~/projects/webcat-site && git checkout main && git pull
    chmod +x scripts/webcat-loop.sh
    ./scripts/webcat-loop.sh    # run once by hand; mailbox is placeholder → exits silently, ~1s
    cat ~/.webcat-loop/loop.log 2>/dev/null || echo "(no log yet — nothing to do, as expected)"

## Install — Part B (in Windows PowerShell) — create the every-2-min alarm clock
    schtasks /create /tn "WebCat AI Loop" /tr "wsl.exe -u webcat-worker -- /home/webcat-worker/projects/webcat-site/scripts/webcat-loop.sh" /sc minute /mo 2 /f

That one line creates a task named **WebCat AI Loop** that fires every 2 minutes. It runs while you're
logged in (fine for the experiment; a locked screen still counts as logged in).

## Control panel (Windows PowerShell)
- See it / next run:   `schtasks /query /tn "WebCat AI Loop" /v /fo LIST`
- Run it right now:    `schtasks /run /tn "WebCat AI Loop"`
- Pause it:            `schtasks /change /tn "WebCat AI Loop" /disable`
- Resume it:           `schtasks /change /tn "WebCat AI Loop" /enable`
- Remove it entirely:  `schtasks /delete /tn "WebCat AI Loop" /f`

## The instant OFF switch (no Windows needed)
Add an empty file `handoff/STOP` to the repo (GitHub → Add file → name it `handoff/STOP` → commit,
or ask Cowork). Every tick sees it and halts — even mid-schedule. Delete it to resume.

## Watching it work
    tail -f ~/.webcat-loop/loop.log     # live log of ticks that did something (empty ticks stay silent)
