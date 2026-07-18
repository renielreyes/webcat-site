"""`status` — the read-only, always-safe orientation command.

Answers the questions a non-technical owner needs in an async system: Is the loop
running or paused? Is anything waiting on me? What's the state of it? Did my last
publish actually go live? It composes the config, the GitHub/live-site provider,
the command log, and the local STOP flag into plain English. It takes no lock and
writes nothing.
"""
from __future__ import annotations

from .provider import ProviderError

HELD_LABEL = "held"


def classify_pr(pr: dict) -> str:
    if HELD_LABEL in [l.lower() for l in pr.get("labels", [])]:
        return "on hold"
    if pr.get("is_draft"):
        return "building"
    return "ready to review"


def compute_status(config, provider, log, stop_active: bool) -> dict:
    """Gather everything status needs into a structured dict (this is what tests assert on)."""
    state: dict = {
        "loop": "paused" if stop_active else "running",
        "github_ok": True,
        "github_error": None,
        "pending": [],
        "last_ship": log.last_ship(),
        "live": provider.live_check(config.live_url),
    }
    try:
        prs = provider.list_open_prs()
        state["pending"] = [
            {"number": p["number"], "title": p["title"], "state": classify_pr(p), "head_sha": p["head_sha"]}
            for p in prs
        ]
    except ProviderError as e:
        state["github_ok"] = False
        state["github_error"] = str(e)
    return state


def render_status(state: dict) -> str:
    lines: list[str] = ["Command Center — status", ""]

    if state["loop"] == "paused":
        lines.append("Loop:    PAUSED — nothing will build or publish until you type `resume`.")
    else:
        lines.append("Loop:    running.")

    if not state["github_ok"]:
        lines.append(f"Pending: couldn't check right now — {state['github_error']}.")
    elif not state["pending"]:
        lines.append("Pending: nothing waiting on you — all caught up.")
    else:
        n = len(state["pending"])
        lead = "Pending: 1 change waiting:" if n == 1 else f"Pending: {n} changes open:"
        lines.append(lead)
        for p in state["pending"]:
            lines.append(f"           #{p['number']} \"{p['title']}\" — {p['state']}")

    ship = state["last_ship"]
    if ship:
        when = ship.get("ts", "?")
        title = ship.get("title", "your last change")
        lines.append(f"Last published: {title} (at {when}).")
    else:
        lines.append("Last published: nothing yet.")

    live = state["live"]
    lines.append(f"Live site: {'OK' if live['ok'] else 'NOT reachable'} — {live['note']}.")

    return "\n".join(lines)
