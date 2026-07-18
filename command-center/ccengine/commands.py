"""Phase 1 commands: run, preview, hold.

Each is a plain function that takes its dependencies explicitly (config, provider,
state store, mailbox) and returns a Result — so the CLI layer handles locking,
logging, and printing, and the logic is unit-tested with fakes. These commands
NEVER merge or deploy; they queue work, show a safe preview, or park a change.
"""
from __future__ import annotations

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
