"""Phase 1 commands: run, preview, hold.

Each is a plain function that takes its dependencies explicitly (config, provider,
state store, mailbox) and returns a Result — so the CLI layer handles locking,
logging, and printing, and the logic is unit-tested with fakes. These commands
NEVER merge or deploy; they queue work, show a safe preview, or park a change.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from .mailbox import MailboxError
from .provider import ProviderError
from .state import Pending, StateStore, now_iso


@dataclass
class Result:
    outcome: str            # 'ok' | 'refused' | 'failed'
    message: str            # plain-English, ready to show the owner
    fields: dict = field(default_factory=dict)
    exit_code: int = 0


def build_task_markdown(task_text: str, run_id: str) -> str:
    return f"""# Task

## What I want
{task_text}

## Where
Only the files this change needs — inside this repository, nothing else.

## Done looks like
The change is made and the site still renders correctly; nothing unrelated is touched.

## Model
Claude (the subscription the worker is signed in with).

## Rules
- The charter (`Infra/AI Executor Charter.md`) is binding. Work ONLY in this repository.
- Branch `handoff/cc-{run_id}`, commit, push, open a PR with a plain-English summary.
- Write `results/cc-{run_id}.json` per the results contract.
- HARD STOP at "PR ready" — never merge, never deploy, never touch DNS/GoDaddy/Azure/WebLab.
- If anything is unclear or risky: stop, and explain plainly in the result file and PR.
"""


def run(cfg, provider, state_store: StateStore, mailbox, task_text: str) -> Result:
    task_text = (task_text or "").strip()
    if not task_text:
        return Result("refused", 'Tell me what to build — e.g.  run "add a contact button".')

    # One change in flight at a time (keeps preview/ship unambiguous + within the preview cap).
    if state_store.get() is not None:
        p = state_store.get()
        return Result("refused",
                      f'You already have a change waiting ({p.label}) — preview, ship, or hold it first.')
    try:
        open_prs = provider.list_open_prs()
    except ProviderError as e:
        return Result("failed", f"Couldn't check GitHub first — {e}.", exit_code=1)
    if open_prs:
        nums = ", ".join(f"#{p['number']}" for p in open_prs)
        return Result("refused",
                      f"There's already an open change ({nums}) — preview, ship, or hold it before starting another.")

    run_id = uuid.uuid4().hex[:8]
    try:
        commit = mailbox.write_task(build_task_markdown(task_text, run_id), message=f"cc: queue task {run_id}")
    except MailboxError as e:
        return Result("failed", f"Couldn't queue the task — {e}.", exit_code=1)

    state_store.set(Pending(task=task_text, created_ts=now_iso()))
    return Result("ok",
                  "Got it — building now. I'll have a preview ready in a few minutes; "
                  "type  status  (or  preview )  to check.",
                  fields={"run_id": run_id, "mailbox_commit": commit})


def preview(cfg, provider, state_store: StateStore) -> Result:
    pending = state_store.get()
    try:
        open_prs = provider.list_open_prs()
    except ProviderError as e:
        return Result("failed", f"Couldn't check GitHub — {e}.", exit_code=1)

    if not open_prs:
        if pending:
            return Result("ok", "Your change is still building — no preview yet. Try  preview  again in a minute.")
        return Result("ok", 'Nothing is being built right now. Start one with  run "...".')
    if len(open_prs) > 1:
        nums = ", ".join(f"#{p['number']}" for p in open_prs)
        return Result("refused",
                      f"There are several open changes ({nums}) — that shouldn't happen with one-at-a-time. "
                      "Tell me and I'll sort it out.")

    pr = open_prs[0]
    url = provider.preview_url(pr["number"])

    st = pending or Pending(task=pr["title"], created_ts=now_iso())
    st.pr_number = pr["number"]
    if url:
        st.previewed_sha = pr["head_sha"]   # pin exactly what the owner reviewed, for ship
    state_store.set(st)

    if not url:
        return Result("ok",
                      f'Change #{pr["number"]} "{pr["title"]}" is built, but its private preview link '
                      "isn't ready yet — try  preview  again in a minute.")

    health = provider.live_check(url)
    tail = "" if health["ok"] else "\n(The link isn't responding yet — give it a moment.)"
    return Result("ok",
                  f'Preview of "{pr["title"]}" (change #{pr["number"]}):\n'
                  f'  {url}\n'
                  f'This is a private test link — not live yet. If it looks right, type  ship  to publish it.{tail}',
                  fields={"pr": pr["number"], "previewed_sha": pr["head_sha"]})


def _await_deploy(provider, sha: str, check_name: str, *, sleep, timeout: float, interval: float):
    """Poll the named deploy check on `sha` until it finishes or we run out of time.
    Returns 'success' | 'failure' | <other conclusion> | 'pending' | None (None = never appeared)."""
    waited = 0.0
    last = provider.deploy_conclusion(sha, check_name)
    while last is None or last == "pending":
        if waited >= timeout:
            break
        sleep(interval)
        waited += interval
        last = provider.deploy_conclusion(sha, check_name)
    return last


def ship(cfg, provider, state_store: StateStore, *,
         sleep=time.sleep, poll_timeout: float = 240.0, poll_interval: float = 6.0) -> Result:
    """Publish the change the owner just previewed.

    Approves and merges EXACTLY the previewed version through the human-merge gate
    (using the owner's locked merge key — never the caged builder), then waits for the
    deploy to finish so it can report the truth: merged vs. actually-live. Refuses unless
    there's a single, previewed, un-held change and the merge key is present on this machine.
    """
    if cfg.merge_token() is None:
        return Result("refused",
                      "Publishing isn't set up on this machine yet — the owner merge key is missing. "
                      "(Ship runs as you, with your own locked key; the builder can never publish.)",
                      exit_code=1)

    pending = state_store.get()
    if pending is None or pending.pr_number is None:
        return Result("refused",
                      'Nothing is ready to publish. Start a change with  run "..."  and  preview  it first.')
    if pending.held:
        return Result("refused",
                      f"Change #{pending.pr_number} is on hold — release it before publishing.")
    if not pending.previewed_sha:
        return Result("refused",
                      "Preview it first, so I publish exactly the version you saw. Type  preview .")

    num = pending.pr_number
    pinned = pending.previewed_sha

    # Did the change move since you previewed it? Friendly message here; the merge below is
    # SHA-pinned too, so even a race can never publish a version you didn't review.
    current = provider.pr_view(num)
    if current is None:
        return Result("failed",
                      f"I couldn't find change #{num} on GitHub anymore — it may have been closed. "
                      "Type  status  to see where things stand.", exit_code=1)
    if current["head_sha"] != pinned:
        return Result("refused",
                      f"Change #{num} was updated after you previewed it. Type  preview  again to see the "
                      "new version, then  ship .")

    title = current["title"] or pending.task

    try:
        provider.approve_pr(num, body="Approved & shipped via Command Center (owner).")
        provider.merge_pr(num, expected_sha=pinned)
    except ProviderError as e:
        return Result("failed",
                      f"Couldn't publish change #{num} — {e}. Your live site was NOT changed; "
                      "type  status , then try  ship  again or  hold  it.", exit_code=1)

    merge_sha = provider.default_branch_sha("main") or ""

    # Deploy-aware: don't claim "live" until the deploy check actually finishes.
    conclusion = None
    if merge_sha:
        conclusion = _await_deploy(provider, merge_sha, cfg.deploy_check,
                                   sleep=sleep, timeout=poll_timeout, interval=poll_interval)
    live = provider.live_check(cfg.live_url)

    state_store.clear()   # this change is done — clear the slot for the next one
    fields = {"pr": num, "merge_sha": merge_sha, "title": title,
              "previewed_sha": pinned, "deploy": conclusion or "unknown"}

    if conclusion == "success" and live["ok"]:
        return Result("ok",
                      f'Published "{title}" (change #{num}). The deploy finished and your live site is up — '
                      "it can take a minute for the newest version to reach everyone.",
                      fields=fields)
    if conclusion == "failure":
        return Result("failed",
                      f'Change #{num} was merged, but the publish step FAILED. Your previously-live site is '
                      "still up and unchanged — nothing broke for visitors. Type  status ; we can re-run the "
                      "publish or start a fix.",
                      fields=fields, exit_code=1)
    # Merged for real, deploy still finishing (slow or timed out) — merged is true, live is pending.
    return Result("ok",
                  f'Merged "{title}" (change #{num}). Publishing is finishing in the background — give it a '
                  "minute, then type  status  to confirm it's live.",
                  fields=fields)


def stop(cfg) -> Result:
    """Instant pause. Write the LOCAL stop file the worker loop checks first (before any network),
    so nothing new builds or publishes. No confirmation — a kill switch must never add friction."""
    sf = cfg.path("stop_file")
    sf.parent.mkdir(parents=True, exist_ok=True)
    already = sf.exists()
    sf.write_text("paused by Command Center\n", encoding="utf-8")
    if already:
        return Result("ok", "Already paused — nothing new will build or publish. Type  resume  to continue.")
    return Result("ok",
                  "Paused. Nothing new will build or publish. (A build already running will finish on its own — "
                  "up to a few minutes — then everything stays stopped.) Type  resume  when you're ready.",
                  fields={"stop_file": str(sf)})


def resume(cfg) -> Result:
    """Clear the pause so the loop runs again. Owner action."""
    sf = cfg.path("stop_file")
    if not sf.exists():
        return Result("ok", "The loop is already running — nothing to resume.")
    try:
        sf.unlink()
    except OSError as e:
        return Result("failed", f"Couldn't clear the pause — {e}.", exit_code=1)
    return Result("ok", "Resumed — the loop is running again. Type  status  to check.",
                  fields={"stop_file": str(sf)})


def hold(cfg, provider, state_store: StateStore, note: str = "") -> Result:
    pending = state_store.get()
    pr_number = pending.pr_number if pending else None

    if pr_number is None:
        try:
            open_prs = provider.list_open_prs()
        except ProviderError as e:
            return Result("failed", f"Couldn't check GitHub — {e}.", exit_code=1)
        if len(open_prs) == 1:
            pr_number = open_prs[0]["number"]
            pending = pending or Pending(task=open_prs[0]["title"], created_ts=now_iso())
            pending.pr_number = pr_number
        else:
            return Result("refused", "There's no single pending change to hold right now.")

    try:
        provider.add_label(pr_number, "held")
        if note.strip():
            provider.add_comment(pr_number, f"Held via Command Center: {note.strip()}")
    except ProviderError as e:
        return Result("failed", f"Couldn't hold the change — {e}.", exit_code=1)

    pending.held = True
    pending.note = note.strip()
    state_store.set(pending)
    return Result("ok",
                  f"Parked change #{pr_number} — it won't publish until you release it. "
                  "The live site is unchanged.",
                  fields={"pr": pr_number})
