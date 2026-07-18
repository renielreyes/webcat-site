#!/usr/bin/env bash
# webcat-loop.sh — the guard the timer runs every tick.
# Reads the APPROVED task from the MAILBOX branch (queuing a task never redeploys),
# builds on top of main, and feeds the task to Claude INLINE (it never lands in the
# working tree, so it can't pollute the PR). Kill switches: a LOCAL stop file
# (instant, checked before any network) plus the legacy git STOP on main. Safety
# belts: single-flight lock, placeholder skip, per-task dedupe, daily cap, timeout,
# turn cap. Runs as the caged webcat-worker user. Read-only mailbox consumer.
set -uo pipefail

# --- config ---
REPO="$HOME/projects/webcat-site"
STATE="$HOME/.webcat-loop"
LOG="$STATE/loop.log"
LOCK="$STATE/run.lock"
LAST_TASK="$STATE/last-task.sha"
LOCAL_STOP="$STATE/STOP"              # the Command Center `stop` writes this (instant kill)
MAILBOX_BRANCH="mailbox"             # tasks arrive here, NOT on main
MAX_RUNS_PER_DAY=20
MAX_TURNS=25
RUN_TIMEOUT="15m"
DRIVER="Infra/driver-prompt.md"
export PATH="$HOME/.local/bin:$PATH"   # so 'claude' is found under systemd

mkdir -p "$STATE"
DAYCOUNT="$STATE/runs-$(date +%F).count"
log(){ echo "$(date -Is) $*" >> "$LOG"; }

# --- single-flight: if a run already holds the lock, leave quietly ---
exec 9>"$LOCK" || exit 0
if ! flock -n 9; then exit 0; fi

# --- LOCAL instant kill switch: checked FIRST, before any network (offline-proof) ---
if [ -f "$LOCAL_STOP" ]; then log "LOCAL STOP present — halting"; exit 0; fi

cd "$REPO" 2>/dev/null || { log "ERROR repo missing at $REPO"; exit 1; }

# --- sync: main = the code base to build on; mailbox = where the task lives ---
git fetch origin main --quiet 2>>"$LOG" || { log "WARN git fetch main failed (offline?)"; exit 0; }
git fetch origin "$MAILBOX_BRANCH" --quiet 2>>"$LOG" || true   # mailbox may not exist yet
git checkout -B main origin/main --quiet 2>>"$LOG"
git clean -fdq 2>>"$LOG"

# --- legacy git STOP on main (secondary kill switch) ---
if [ -f handoff/STOP ]; then log "git STOP flag present — halting"; exit 0; fi

# --- read the approved task from the mailbox branch (do nothing if there isn't one) ---
if ! git rev-parse --verify --quiet "origin/$MAILBOX_BRANCH" >/dev/null; then exit 0; fi
TASK=$(git show "origin/$MAILBOX_BRANCH:handoff/NEXT-TASK.md" 2>/dev/null || true)
[ -z "$TASK" ] && exit 0
printf '%s' "$TASK" | grep -qi "placeholder" && exit 0

# --- dedupe: already ran this exact task? ---
CUR=$(printf '%s' "$TASK" | sha256sum | cut -d' ' -f1)
if [ -f "$LAST_TASK" ] && [ "$(cat "$LAST_TASK")" = "$CUR" ]; then exit 0; fi

# --- daily cap (runaway-spend backstop) ---
COUNT=$(cat "$DAYCOUNT" 2>/dev/null || echo 0)
if [ "$COUNT" -ge "$MAX_RUNS_PER_DAY" ]; then log "DAYCAP $MAX_RUNS_PER_DAY reached — halting till tomorrow"; exit 0; fi

# --- NEW real task: record it FIRST (a crash won't re-run it), then build with the task fed INLINE ---
echo "$CUR" > "$LAST_TASK"
echo $((COUNT+1)) > "$DAYCOUNT"
log "RUN start task-sha=${CUR:0:12} run#$((COUNT+1))"
PROMPT="$(cat "$DRIVER")

## TASK FOR THIS RUN (approved via the mailbox — this is the task to do)
$TASK"
timeout "$RUN_TIMEOUT" claude -p "$PROMPT" --dangerously-skip-permissions --max-turns "$MAX_TURNS" >> "$LOG" 2>&1
log "RUN end rc=$?"
exit 0
