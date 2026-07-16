# Task

## What I want
A small, clearly-temporary TEST marker on the holding page, so we can watch a change go from build →
preview → live → rollback and prove the command flow works end to end.

In `Site/holding-page/index.html`, add exactly ONE new line inside the existing `<footer>` — right after
the "family" line — reading exactly:

    AI Brain command-test · 2026-07-16 — temporary, safe to remove

Style it subtly (muted color, ~11px, on its own line) so it is clearly visible but unobtrusive. Change
nothing else anywhere in the file or repo.

## Where
`Site/holding-page/index.html` — footer only.

## Done looks like
The holding page footer shows that one marker line; the rest of the page renders exactly as before.

## Model
Claude (the subscription the worker is signed in with).

## Rules
- The charter (`Infra/AI Executor Charter.md`) is binding. Work ONLY in this repository.
- Branch `handoff/cmd-test.r1`, commit, push, open a PR with a plain-English summary.
- Write `results/cmd-test.r1.json` per the results contract.
- HARD STOP at "PR ready" — never merge, never deploy, never touch DNS/GoDaddy/Azure/WebLab.
- If anything is unclear or risky: stop, and explain plainly in the result file and PR.
