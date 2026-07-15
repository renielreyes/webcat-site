# Cage verification certificate — 2026-07-14

This certificate records the OS-level fence checks required by the charter
(`Infra/AI Executor Charter.md`, "The OS-level fence") **before executor run #1**.

## Environment

- **Date:** 2026-07-14
- **Host:** "Dragon" NUC, WSL2 Ubuntu-24.04
- **Executor user:** `webcat-worker` (dedicated, low-privilege)

## Negative tests (all behaved as required, BEFORE the first run)

| Check | Result |
|---|---|
| `whoami` | → `webcat-worker` |
| `az account show` | → command not found (no Azure CLI, no Azure identity in cage) |
| `gh auth status` (pre-key) | → command not found (no GitHub identity in cage) |
| `ls /home/reny` | → Permission denied |
| `ls /home/reny/projects/weblab` | → Permission denied (WebLab unreachable) |
| `git clone` of this public repo | → succeeded (read allowed by design) |

## Toolchain

- Claude Code **2.1.210**, installed user-local (`~/.local/bin`).
- Auth = owner's Claude subscription (**no API key on the box**).

## Credential

- A single **fine-grained GitHub token**, scoped to **THIS repo only**.
- Permissions: **Contents: write** + **Pull requests: write**.
- **90-day** expiry, stored in the worker's `gh` config.
- **Rotated same day** after partial on-screen exposure (hygiene rule: exposed = rotated).

## Conclusion

**Charter fences verified prior to run #1.**
