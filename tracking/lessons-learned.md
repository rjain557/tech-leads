# Lessons Learned — tech-leads pipeline

Append after every scan run. Format: `- YYYY-MM-DD: <lesson> — <why/context>`

Never delete. Mark obsolete ones with `[OBSOLETE]` and a reason.

---

## Active

- 2026-04-17: Outreach defaults to draft-only — per user direction; cold B2B email auto-send risks the whole tenant's sender reputation; requires explicit user flip in targeting.yml to enable.
- 2026-04-17: No ICP constraints — per user direction any company whose posted role could be covered by a Technijian service is a candidate; do not auto-filter by company size or industry.
- 2026-04-17: Weekly cadence not daily — B2B hiring signals don't change daily; weekly avoids rate-limit burn and keeps lead packets digestible.
- 2026-04-17: Outreach email sequence is link-free and case-study-free — rjain handles the meeting and proposal stages personally and speaks to similar work from his own memory, so no written case-study artifact is needed at any stage of the pipeline.
- 2026-04-17: technijian.com has no case-study pages — only /our-results/ which is a testimonials wall (short Google-review-style quotes tagged by vertical: Pharmaceutical, Dental, Medical Equipment, Auto Group, Financial Services, Hospitality, Medical Management). If a case-study library is ever wanted for SEO or pre-meeting buyer skim, it would need to be built from scratch — but that's a marketing-site concern, not a pipeline concern.
- 2026-04-17: Keyword match is a prefilter, not a qualifier — Cisco security-engineer postings pass keyword filters but Cisco is a security vendor, not an MSP customer. Stage 2 must be LLM-driven. Implemented `scripts/qualify_leads.py` (batched Sonnet 4.6, 20 leads/call, $0.35 per 180-lead run).
- 2026-04-17: Qualifier is binary — qualified or rejected. No human triage queue, no `leads/needs-review/`. Per user: "if they need review just reject them — i want a fully automated pipeline." Enforced in `route_lead()`.
- 2026-04-17: Claude Code OAuth token cannot do bulk API calls while an interactive session is active — 429 every request even with 60s backoff. MUST use a separate `anthropicApiKey`. `load_auths()` prefers API key, falls back to OAuth only on 401/403.
- 2026-04-17: SerpAPI google_jobs location gotcha — `"Irvine, CA"` returns HTTP 400 `Unsupported location`. Use `"Irvine, California, United States"`. Fixed in `portals.yml`.
- 2026-04-17: SerpAPI google_jobs remote filter — `chips=requirements:remote` returns zero results for every query (silently). Correct form is `ltype=1` + `location="United States"`. Fixed in `scan_jobs.py:fetch_serpapi_google_jobs`. This bug was hiding the entire remote-US lead pool.
- 2026-04-17: PowerShell 5.1 breaks on UTF-8 non-ASCII in `.ps1` files — em-dashes, arrows, CJK chars produce `TerminatorExpectedAtEndOfString` parser errors at a random later line. Windows Task Scheduler actions still call `powershell.exe` (5.1) by default. Write all `.ps1` files pure-ASCII.
- 2026-04-17: Windows Python stdout default is cp1252 — crashes printing CJK / fullwidth parens in scraped company names (e.g. `JV Express Pvt Ltd （Variovox）`). Fix: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at top of any script that prints scraped strings.
- 2026-04-17: Job aggregator reposts (Virtual Vocations, Flexjobs, Jobgether, Jobs via Dice, WhatJobs, JobLeads, BeBee) surface in SerpAPI results with thin JDs — qualifier rejects them but they cost a credit per occurrence. Add to a prefilter exclusion list in `scan_jobs.py` to save credits.

## Keywords that worked

_(empty — populate after first real run)_

## Keywords that wasted time

_(empty)_

## False-positive patterns

_(empty)_

## New strong-signal ideas to try

_(empty)_
