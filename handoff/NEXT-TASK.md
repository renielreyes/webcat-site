# Task

## What I want
A small command-line tool at `scripts/zone-diff.py` that compares two DNS zone snapshot text
files ("before" and "after") and reports what changed — so a human can verify, after a DNS edit,
that ONLY the intended records changed.

## Where
New `scripts/` folder in this repository. Plain Python 3, standard library only (no pip installs).

## Done looks like
- `python3 scripts/zone-diff.py before.txt after.txt` prints three clearly labeled sections:
  ADDED, REMOVED, and CHANGED (same record name+type but different value or TTL), then a one-line
  verdict. Exit code 0 when the files match, 1 when there are differences, 2 on usage error.
- Tolerant input parsing: ignores blank lines and comment lines (starting with `#` or `;`),
  case-insensitive for record names and types, collapses repeated whitespace. Lines that parse as
  "name type value..." are compared as records; unparseable lines are compared as plain text.
- `python3 scripts/zone-diff.py --selftest` runs built-in example cases (identical, added,
  removed, changed) and prints PASS/FAIL per case; exits 0 only if all pass.
- Usage instructions in a comment block at the top of the script, plus a short `scripts/README.md`
  with one worked example.

## Model
Claude (the subscription the worker is signed in with).

## Rules
- The charter (`Infra/AI Executor Charter.md`) is binding. Work ONLY in this repository.
- Branch `handoff/zone-diff.r1` → commit → push → open a PR with a plain-English summary.
- Write `results/zone-diff.r1.json` per the results contract (include it in the PR).
- HARD STOP at "PR ready" — never merge, never deploy, never touch DNS/GoDaddy/Azure/WebLab.
- If anything is unclear or risky: stop, and explain in plain English in the result file and PR.
