# webcat-site

The website repository for **Webcat.net Corp** (webcat.net) — and **trial #1 of the AI Brain
headless-executor loop** (see `Infra/AI Executor Charter.md`; the charter is binding once merged).

## What's here

```
Site/holding-page/     ← the live site (Azure Static Web Apps deploys this on merge to main)
  index.html           ← holding page v0
  staticwebapp.config.json  ← unknown paths redirect to domains.webcat.net (old storefront bookmarks)
Infra/
  AI Executor Charter.md    ← the executor's binding guardrails (one page, forever)
  DNS Switchover Runbook.md ← v2, council-hardened; HUMAN-ONLY steps tagged
  dns-snapshot-2026-07-13.md ← pre-change DNS baseline (replace with full A0 zone export)
handoff/               ← the AI Brain mailbox (tasks in, results back as PRs)
.github/workflows/gitleaks.yml ← secret scan on every push/PR
```

## Rules of the repo

- **Public-destined content only.** No secrets, no WebLab material, no client names until approved.
- **Merge to `main` = production deploy** (once www.webcat.net points at Azure). Humans merge; nothing else does.
- **The AI executor** works via `handoff/` tasks → branch → PR only. It never holds GoDaddy/Azure credentials.
- Before the first executor run: enable branch protection on `main` (needs GitHub Pro on a private repo — either flip this repo public or upgrade; decide at canary time).

## Status

- 2026-07-13 — repo created; holding page ready; cutover pending (see runbook Phase 0–B).
- 2026-07-14 — relay loop wired (driver, mailbox rules, results contract, cage verified); repo public; main branch protected.
