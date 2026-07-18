# Task

## What I want
Add a small, clearly-temporary test marker to the bottom of the holding page footer, reading exactly: Command Center live test — safe to remove. Style it small and muted, on its own line. Change nothing else.

## Where
Only the files this change needs — inside this repository, nothing else.

## Done looks like
The change is made and the site still renders correctly; nothing unrelated is touched.

## Model
Claude (the subscription the worker is signed in with).

## Rules
- The charter (`Infra/AI Executor Charter.md`) is binding. Work ONLY in this repository.
- Branch `handoff/cc-f9337d04`, commit, push, open a PR with a plain-English summary.
- Write `results/cc-f9337d04.json` per the results contract.
- HARD STOP at "PR ready" — never merge, never deploy, never touch DNS/GoDaddy/Azure/WebLab.
- If anything is unclear or risky: stop, and explain plainly in the result file and PR.
