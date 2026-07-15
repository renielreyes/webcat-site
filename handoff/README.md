# handoff/ — the AI Brain mailbox

This folder is how work reaches the AI executor and how the executor is kept on a short leash.
The charter (`Infra/AI Executor Charter.md`) is binding; if anything here ever conflicts with it,
the charter wins.

## How tasks arrive

- A task is placed in `handoff/NEXT-TASK.md`, using the template already in that file.
- Tasks are authored **only by Reny or Cowork**. Nothing else may author a task.
- If `NEXT-TASK.md` is still the placeholder (no real task selected), a run does nothing and exits.

## The STOP flag (kill switch)

- If a file named `handoff/STOP` exists, **any run must halt immediately and do nothing** —
  no reading tasks, no branching, no commits, no PRs.
- **Absence of `handoff/STOP` = permitted to run.** Its presence is checked every time.

## What every run must do

1. Do exactly what `NEXT-TASK.md` asks — **only inside this repository**.
2. End by writing a result record under `results/` (see `results/README.md` for the contract).
3. If work was produced, open a pull request with a plain-English summary.

## What runs must NEVER do

- **Never merge.** **Never push to `main`.** Merging to `main` is a human action (and the only deploy).
- **Never touch anything outside this repository** — no DNS, GoDaddy, Azure, email, WebLab, other repos,
  or any credentials beyond the single repo-scoped GitHub token.

A run's hard stop is "PR ready." Everything past that is a human's decision.
