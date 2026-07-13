---
type: charter
product: AI Brain — headless executor trial #1 (webcat-site repo)
status: DRAFT v1 — becomes binding when committed as the new repo's first file
source: Council fix #1 (2026-07-13) reconciled with "[C] AI Brain — Automated Git-Relay Loop (Design + Council Review).md" and the Level-1 Git Relay runbook. Where they conflict, THIS charter wins.
rule: one page, forever. If this needs a second page, the trial has scope-crept — stop and re-scope.
---

# AI Executor Charter — webcat-site trial

**Purpose.** Trial the AI Brain git-relay loop on the website repo — real work, zero blast radius.
WebLab is out of bounds by construction, not by promise.

## Credentials the executor NEVER holds
GoDaddy (any). Azure (any — portal, az, SWA deploy tokens). GitHub tokens beyond a fine-grained
token scoped to **this one repo, Contents + Pull-requests write only**. No WebLab checkout, no
WebLab secrets, no SSH keys to anything else. All DNS/portal actions are **HUMAN-ONLY, forever**
(the DNS Switchover Runbook is human-executed; the executor may only *draft* edits to it).

## The OS-level fence (prove it before run #1 — negative tests)
Dedicated WSL2 distro or user (e.g. `webcat-worker`) whose home contains ONLY `~/projects/webcat-site`.
Before the first run, from inside that environment, ALL of these must fail:
`az account show` → fails · `gh auth status` → no auth beyond the repo-scoped token ·
read of any WebLab path → fails · a deliberate probe task "read the WebLab checkout" → refused/fails.

## Autonomy matrix
| May, unattended | Never |
|---|---|
| Read/edit files in this repo | Merge, or push to `main` (branch protection enforces) |
| Commit to `handoff/<id>.<runId>` branches | Deploy anything (merge-to-main by Reny is the ONLY deploy) |
| Open a PR with summary + screenshots | Touch DNS, GoDaddy, Azure, email, WebLab, other repos |
| Run builds/tests/screenshots locally | Fetch the web (off by default; allowlist only if a task needs it) |

## Bounded runs (the money + runaway fences)
`timeout` wall-clock wrapper on every `claude -p` · `--max-turns` low (4–6) until real cost data ·
auth = Claude subscription or a spend-capped key (confirm which BEFORE run #1; add the answer here) ·
no self-rescheduling · `handoff/STOP` file = kill switch, checked every fire · circuit breaker:
2 consecutive failures → halt + tell Reny. Failures are PUSHED to the morning briefing — silence never means success.

## Tasks, logging, content
Task files live in `handoff/` in the repo, authored ONLY by Reny or Cowork (versioned, diffable).
Every run commits an append-only log: `results/<id>.<runId>.json` (status, cost, sha, summary) — kept
publishable-clean (future AI-services case study). Repo contains **public-destined content only**:
no secrets (gitleaks pre-commit from commit #1), no WebLab material, no client names until approved (O2).

## Model policy (differs from WebLab — deliberately)
This repo is public marketing content: **local NUC models and GLM are permitted** for execution.
10/80/10 stands: plan (Cowork/best model) → execute (cheap brain) → audit (best model reviews the PR
before Reny merges). No regulated data exists here; if any ever enters this repo, the WebLab fence rules apply.

## Sequencing (council-mandated)
The trial does NOT gate the website cutover. Order: human-executed DNS cutover → Phase C verified →
THEN executor canary. **Canary task #1 (read-only):** write `scripts/zone-diff.py` comparing two DNS
snapshot files and reporting unintended changes — useful forever, touches nothing live.

*Signed by merge: committing this file to `main` of webcat-site makes it binding. Amendments = PR + human merge.*
