#!/usr/bin/env bash
# webcat-loop.sh — the guard the timer runs every tick.
# CHEAP checks first (git fetch + grep). Only wakes Claude on a genuinely NEW approved task.
# Safety belts: single-flight lock, STOP flag, placeholder skip, per-task dedupe, daily cap,
# wall-clock timeout, turn cap. Runs as the caged webcat-worker user. Read-only mailbox consumer.
set -uo pipefail

# --- config ---
REPO="$HOME/projects/webcat-site"
STATE="$HOME/.webcat-loop"
LOG="$STATE/loop.log"
LOCK="$STATE/run.lock"
LAST_TASK="$STATE/last-task.sha"
MAX_RUNS_PER_DAY=20
MAX_TURNS=25
RUN_TIMEOUT="15m"
DRIVER="Infra/driver-prompt.md"
export PATH="$HOME/.local/bin:$PATH"   # so 'claude' is found under systemd/Task Scheduler

mkdir -p "$STATE"
DAYCOUNT="$STATE/runs-$(date +%F).count"
log(){ echo "$(date -Is) $*" >> "$LOG"; }

# --- single-flight: if a run already holds the lock, leave quietly ---
exec 9>"$LOCK" || exit 0
if ! flock -n 9; then exit 0; fi

cd "$REPO" 2>/dev/null || { log "ERROR repo missing at $REPO"; exit 1; }

# --- sync to main exactly (mailbox is read-only to the loop) ---
git fetch origin main --quiet 2>>"$LOG" || { log "WARN git fetch failed (offline?)"; exit 0; }
git checkout -B main origin/main --quiet 2>>"$LOG"
git clean -fdq 2>>"$LOG"

# --- STOP flag = git-native kill switch ---
if [ -f handoff/STOP ]; then log "STOP flag present — halting"; exit 0; fi

# --- real task, or still the placeholder? ---
if grep -qi "placeholder" handoff/NEXT-TASK.md; then exit 0; fi

# --- dedupe: already ran this exact task? ---
CUR=$(sha256sum handoff/NEXT-TASK.md | cut -d' ' -f1)
if [ -f "$LAST_TASK" ] && [ "$(cat "$LAST_TASK")" = "$CUR" ]; then exit 0; fi

# --- daily cap (runaway-spend backstop) ---
COUNT=$(cat "$DAYCOUNT" 2>/dev/null || echo 0)
if [ "$COUNT" -ge "$MAX_RUNS_PER_DAY" ]; then log "DAYCAP $MAX_RUNS_PER_DAY reached — halting till tomorrow"; exit 0; fi

# --- NEW real task: record it FIRST (a crash won't re-run it), then run ---
echo "$CUR" > "$LAST_TASK"
echo $((COUNT+1)) > "$DAYCOUNT"
log "RUN start task-sha=${CUR:0:12} run#$((COUNT+1))"
timeout "$RUN_TIMEOUT" claude -p "$(cat "$DRIVER")" --dangerously-skip-permissions --max-turns "$MAX_TURNS" >> "$LOG" 2>&1
log "RUN end rc=$?"
exit 0
