# DNS snapshot — webcat.net — 2026-07-13 (external queries)

> Baseline captured via public DNS from the Cowork session, cross-checked twice on 2026-07-13
> (initial recon + council live re-verification). **Replace/extend with the full GoDaddy zone
> export at runbook step A0** — this external view cannot see records that don't resolve publicly.

| Record | Type | Value | TTL | Notes |
|---|---|---|---|---|
| webcat.net | NS | ns23.domaincontrol.com, ns24.domaincontrol.com | — | GoDaddy DNS |
| webcat.net | MX | 10 mx1.improvmx.com · 20 mx2.improvmx.com | (A0) | **EMAIL — never edit** |
| webcat.net | TXT | "v=spf1 include:spf.improvmx.com ~all" | (A0) | **EMAIL — never edit** |
| webcat.net | TXT | "MS=ms47877938" | (A0) | old Microsoft verification |
| webcat.net | A | 3.33.130.190 · 15.197.148.33 | (A0) | GoDaddy forwarding/parking |
| www.webcat.net | CNAME | cdrapplication.securepaynet.net | **3600s** (verified) | reseller storefront binding |
| email.webcat.net | A | 15.197.155.180 · 76.223.17.250 | (A0) | GoDaddy template — leave |
| domains.webcat.net | — | NXDOMAIN | — | free (storefront's future home) |
| webcat.net | CAA | none | — | cert issuance cannot be CAA-blocked |
| webcat.net | DMARC | none | — | candidate future additive record (p=none) |

## Reseller Control Center (screenshot on file, 2026-07-13)

- Standard Storefront Domain slot: **www.webcat.net** ← ROLLBACK VALUE
- Default storefront URL (always live): **www.secureserver.net?pl_id=111815**
- Semantics: **single slot, REPLACE** — no parallel custom domains.

## rookieshots.com (out of scope; recorded for later cleanup)

- NS ns43/ns44.domaincontrol.com · A 76.223.67.189/13.248.213.45 (parked)
- MX 0 rookieshots-com.mail.protection.outlook.com (leftover Outlook — cleanup someday)
- TXT "v=spf1 include:secureserver.net -all" · "MS=ms63604310"
