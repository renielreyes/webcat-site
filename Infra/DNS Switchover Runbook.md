# DNS Switchover Runbook — webcat.net · v2

**Version:** 2.0 (2026-07-13) — supersedes v1. Incorporates all 10 council fixes (`Council/Website Plan
Council 2026-07-13.md`) and the live RCC recon finding: the storefront custom-domain is a **single slot
with REPLACE semantics**, so the storefront move and the www flip now happen in **one coordinated window**.

**Goal:** New company site at www.webcat.net · reseller storefront at domains.webcat.net ·
reny@webcat.net email never interrupted · $0/month.

**Actor legend:** 🧑 **HUMAN-ONLY** (Reny at the keyboard — never delegated to any AI executor) ·
🤝 **guided** (Reny clicks, Claude watches/verifies) · 🤖 **Claude** (docs, files, checks from the cloud).
**Standing rule: the AI executor never receives GoDaddy or Azure credentials and never performs any step
in this runbook.** It may only *draft* edits to this document.

---

## 1. Current state (live-verified 2026-07-13 — re-verify at A0)

| Record / setting | Value | TTL | Meaning |
|---|---|---|---|
| NS | ns23/ns24.domaincontrol.com | — | DNS managed at GoDaddy — stays |
| MX | 10 mx1.improvmx.com · 20 mx2.improvmx.com | capture at A0 | **Email. NEVER EDITED.** |
| TXT (SPF) | v=spf1 include:spf.improvmx.com ~all | capture at A0 | **Email. NEVER EDITED.** |
| TXT | MS=ms47877938 | capture at A0 | old MS verification — leave |
| www CNAME | cdrapplication.securepaynet.net | **3600s** (verified) | storefront binding — the flip target |
| apex A | 3.33.130.190 / 15.197.148.33 | capture at A0 | GoDaddy forwarding/parking IPs |
| email.webcat.net | A 15.197.155.180 / 76.223.17.250 | capture at A0 | unknown GoDaddy template — leave |
| domains.webcat.net | NXDOMAIN | — | free — storefront's new home |
| RCC Storefront Domain slot | **www.webcat.net** (screenshot 2026-07-13) | — | **single slot, REPLACE semantics** — rollback value |
| RCC default storefront URL | www.secureserver.net?pl_id=111815 | — | always live — the safety net |
| DMARC / CAA | none / none (verified) | — | CAA can't block cert issuance |
| Domain renewal | Jul 1 2027 · $24.99/yr | — | no action |

## 2. Target state

www.webcat.net → Azure SWA (new site) · webcat.net apex → 301 to www · domains.webcat.net → storefront
(RCC slot) · MX/SPF **identical** · monitoring live with alarms off-domain.

---

## Phase 0 — Accounts & pipeline (any day; zero visitor impact)

| # | Actor | Step |
|---|---|---|
| 0.1 | 🧑 | Confirm **MFA ON** for GoDaddy and Azure logins; credentials in a password manager. (The GoDaddy login is the one thing that can actually kill email.) |
| 0.2 | 🤝 | Create private GitHub repo **webcat-site** (the same repo the AI-executor trial will use later). First commits: `Site/holding-page/`, `Infra/AI Executor Charter.md`, this runbook, `.gitignore` (.env, *.key), gitleaks pre-commit. Branch protection on `main` (require PR, no force-push). |
| 0.3 | 🤝 | Create Azure **Static Web App** from the repo (app root `Site/holding-page/`). **Verify the plan reads FREE in the portal after creation** — the picker has defaulted to Standard. Deploys happen ONLY via merge to `main`. |
| 0.4 | 🤝 | Add `staticwebapp.config.json`: unknown paths → redirect to `https://domains.webcat.net` (years of storefront bookmarks must not hit a raw 404). Add the transition line to the page: “Looking for the domain storefront? It moved to domains.webcat.net.” |
| 0.5 | 🤝 | **Redeploy rehearsal:** change one word → PR → merge → confirm it redeploys at `<app>.azurestaticapps.net`. This proves the emergency-fix path before DNS ever moves. |
| 0.6 | 🧑 | **Outbound email:** configure ImprovMX SMTP (or Gmail send-as) for reny@webcat.net. Pass = a sent message shows **SPF=pass** in its received headers. Do this BEFORE the site is public — every CTA on the page is a mailto. |

## Phase A — Prep (additive only; storefront & email untouched)

| # | Actor | Step |
|---|---|---|
| A0 | 🧑+🤖 | **Fresh zone snapshot:** export/screenshot EVERY record + TTL from GoDaddy DNS; commit to webcat-site as `Infra/dns-snapshot-<date>.txt`. Claude re-runs external checks the same day. **Abort if anything differs from §1** until reconciled. All later verification = **zone-diff vs A0** (“only intended changes”). |
| A1 | 🧑 | **Email baseline (same-day):** send att.net → reny@webcat.net (arrives) and reply as reny@ (SPF=pass). A coincident ImprovMX outage must not masquerade as cutover damage later. |
| A2 | 🧑 | **Rollback stopwatch:** add a throwaway TXT `_rbtest`, time the edit end-to-end, delete it. Real number replaces the old “60 seconds” folklore. |
| A3 | 🧑 | **Lower www CNAME TTL 3600 → 600 seconds.** Value unchanged! Only TTL. Wait ≥ 1 hour (one old-TTL period) before Phase B. Restore to 3600 a day after Phase C passes. |
| A4 | 🧑 | **Pre-issue the SSL cert:** Azure SWA → Custom domains → add `www.webcat.net` via **TXT validation** (additive TXT record; www keeps serving the storefront). **GATE: portal shows domain/cert = Ready before any Phase B.** Not Ready in 60 min → stop, nothing has changed for visitors. |
| A5 | 🧑 | **Apex-HTTPS pre-test:** enable GoDaddy Forwarding for apex → `https://www.webcat.net` (301). Safe now — www still serves the storefront. Immediately re-check MX/SPF (forwarding rewrites only apex A records; decline any prompt touching anything else). Test `https://webcat.net` days early: if it throws a cert error, ACCEPT http-only apex and standardize every published URL on https://www.webcat.net. |
| A6 | 🤖 | Pre-create UptimeRobot free monitors (paused): www keyword “Webcat”, domains.webcat.net, apex redirect. **All alerts → reniel.reyes@att.net** (never reny@ — an MX break must not eat its own alarm). Enable ImprovMX alerts too. |

**Preconditions gate — do not open the Phase B window until ALL are true:**
cert Ready ✓ · redeploy rehearsed ✓ · TTL at 600s for ≥1 hr ✓ · same-day email baseline ✓ ·
zone snapshot committed ✓ · outbound send-as working ✓ · monitors pre-created ✓ · rollback timed ✓ ·
quiet hour chosen ✓ · RCC rollback screenshot on file ✓ (2026-07-13, or re-shoot).

## Phase B — THE WINDOW (one sitting, ~15–30 min, low-traffic hour)

> RCC’s single slot REPLACES www the moment it changes — B1→B3 run back-to-back, no days between.
> Worst case mid-window: www briefly unbound (minutes, at 600s TTL) while the storefront stays
> reachable at its default URL. Claude on watch throughout.

| # | Actor | Step |
|---|---|---|
| B1 | 🧑 | RCC → Settings → Storefront Domains: change the slot from `www.webcat.net` to **`domains.webcat.net`**. GoDaddy may auto-write the CNAME (DNS is in-account) — note exactly what it says/creates. If manual: add CNAME `domains` → the exact target RCC displays. |
| B2 | 🧑 | Verify `https://domains.webcat.net` serves the storefront: **run a domain search AND walk to the secure-checkout page render** (the money path — checkout hopping to the default secure URL is documented/normal). |
| B3 | 🧑 | GoDaddy DNS: edit **www CNAME** value → `<app>.azurestaticapps.net`. (Cert already issued at A4, so no cert-error window.) |
| B4 | 🤝 | Verify `https://www.webcat.net` = holding page **with padlock**; `http://` redirects to `https://`. |
| B5 | 🤝 | Verify apex per A5’s accepted behavior (`curl -sIL http(s)://webcat.net` → 301 → https://www.webcat.net). |
| B6 | 🤖 | Zone-diff vs A0: **only** the intended changes (www value, domains CNAME, apex forwarding artifacts, the A4 TXT). MX/SPF byte-identical. |

## Phase C — Verify (immediately after B)

1. 🤝 www: padlock, page renders, one **non-root path** (e.g. /anything) redirects to domains.webcat.net.
2. 🤝 Storefront: search + cart + checkout-page render on domains.webcat.net.
3. 🧑 Email inbound: att.net → reny@ arrives. 4. 🧑 Email outbound: reply as reny@, **SPF=pass**.
5. 🤖 Re-run all external DNS checks against ns23/ns24 directly AND one public resolver; re-check after one full TTL.
6. 🤝 Un-pause UptimeRobot monitors; confirm first green checks.
7. 🤖 Update dashboard; log completion. **A day later:** restore www TTL to 3600s; monthly zone-diff reminder.

## Rollback (any point; honest timings)

| Undo | How | Time |
|---|---|---|
| www → storefront again | RCC slot back to `www.webcat.net` (per screenshot) AND www CNAME back to `cdrapplication.securepaynet.net` | ~2 min edits + ≤600s propagation |
| domains.webcat.net | Leave or remove the CNAME — harmless either way | — |
| Apex forwarding | Turn Forwarding off; apex A records revert to A0 snapshot values (verify) | ~1 min + TTL |
| Email | Nothing to undo — never touched. **Verify anyway** (inbound + outbound + zone-diff) | 5 min |
| **After ANY rollback** | Load www · storefront search · email pair-test · zone-diff vs A0 | 10 min |

## Do-NOT-touch (amended per council)

Existing **MX and SPF records are never EDITED or DELETED** on any path. *Additive* email-auth records
(DKIM; DMARC starting at `p=none`) are permitted — with explicit human approval, as their own change,
never during the cutover window. NS records / nameservers: never. `email.webcat.net` + anything not named
here: never. rookieshots.com: separate project. **The AI executor: no GoDaddy, no Azure, ever.**

## Later (not this runbook)

DMARC p=none monitoring record → then quarantine when data is clean · swap public mailto to a rotatable
`hello@` ImprovMX alias (reny@ is the WebLab admin identity — don’t publish the admin login as the
scrapeable catch-all) · payee setup in RCC (**$82.17 waiting**) · rookieshots.com site + MX cleanup ·
weblab.webcat.net alias · self-host fonts · og-image polish.
