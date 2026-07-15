# Task

*(Placeholder — no task selected. The loop skips this file while it contains the word
"placeholder", and halts entirely if a `handoff/STOP` file exists. Cowork or Reny replaces
this with a real task via a pull request; merging that PR is the approval that lets the loop run it.)*

## What I want
(One or two plain sentences.)

## Where
(A page, file, or folder hint. Rough is fine.)

## Done looks like
(How we'll know it worked.)

## Model
(local/free · GLM (cheap) · Claude Sonnet · Claude Opus · "Cowork, you pick")

## Rules
- The charter (`Infra/AI Executor Charter.md`) is binding. Work ONLY in this repository.
- Branch `handoff/<short-name>`, commit, push, open a PR with a plain-English summary.
- Write a result JSON under `results/` per the results contract.
- HARD STOP at "PR ready" — never merge, never deploy, never touch DNS/GoDaddy/Azure/WebLab.
- If anything is unclear or risky: stop, and explain in plain English in the result file and PR.
