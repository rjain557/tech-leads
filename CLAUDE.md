# Technijian Lead-Generation Pipeline

## Project Purpose

Automated B2B lead-generation pipeline for Technijian (Orange County MSP). Scans job boards for companies whose hiring activity signals a need for Technijian services (My IT, My AI, My Cloud, My Compliance, My Continuity, My Dev, My Office, My SEO, My Security, My AI Lead Gen), scores each lead, drafts tailored outreach, and sends ready-to-review lead packets to rjain@technijian.com.

**Inverted "Callie" pattern:** instead of finding jobs that fit a candidate, we find **companies posting jobs** that fit Technijian's service catalog. A company hiring a HIPAA Compliance Officer is a lead for My Compliance. A company hiring its first/solo IT admin is a lead for My IT (MSP outsourcing opportunity). Etc.

## Source of Truth

| File | What it is |
|------|------------|
| `config/services.yml` | Service catalog. One entry per Technijian service with pitch, pain signals, buyer titles, signal job titles, signal keywords, strong signals. |
| `config/portals.yml`  | Job boards to scan (Indeed, LinkedIn, ZipRecruiter, Glassdoor, Google Jobs, Dice) + two scopes: local (60mi Irvine) and remote-US. |
| `config/targeting.yml` | ICP rules, scoring weights, dedup keys, outreach mode. Per user direction: **no company-size or industry constraints** — if a company could use a Technijian service, they're a candidate. |
| `tracking/known-companies.json` | Dedup + history. Every company we've reported, bucketed by service. |
| `tracking/lead-log.md` | Human-readable log of every lead surfaced, scored, and reported. |
| `tracking/lessons-learned.md` | Self-improving loop. Append after every run. |

## Outreach Mode — DRAFT-ONLY by default

**Never auto-send outreach emails.** Mode is set in `config/targeting.yml` → `outreach.mode: draft_only`. Drafts land in `templates/drafts/{YYYY-MM-DD}/{company-slug}.md` (email body) + `.json` (metadata). User reviews and sends manually.

To enable auto-send: user must explicitly change `outreach.mode` to `auto_send` AND approve the first batch in-conversation. Never flip it on Claude's own initiative.

If/when auto-send is enabled, use the M365 Graph API pattern from `D:\vscode\technijian-admin-job-postings\job-postings\Scripts\6-SendEmail.ps1` (client-credentials flow, `sendMail` endpoint, dedup against Sent Items). Respect `rate_limit_per_day: 50` hard cap.

## Scoring Model (summary — see targeting.yml for weights)

```
score = base(1.0)
      + 1.5 × title_match (exact signal_job_title hit)
      + 0.5 × keyword_match (capped at 2.0 total)
      + 1.5 if strong_signal pattern matches
      + 1.0 if local scope (60mi Irvine)
      + 0.5 if matches >1 service
      + recency_bonus (≤3d: +0.5, ≤7d: +0.2)
```

- `score ≥ 4.0` → **HOT** — auto-draft outreach, file under `leads/active/`
- `2.5 ≤ score < 4.0` → **WARM** — logged, no draft
- `score < 2.5` → skip

## Daily / Weekly Pipeline

Cadence is **weekly** (per `portals.yml` → `scan_strategy.cadence: weekly`). Daily is overkill for B2B lead-gen and torches rate limits.

1. **Load config** — services.yml, portals.yml, targeting.yml
2. **Render queries** — for each enabled service × each portal × each scope → generate URL list (see `scripts/scan_jobs.py`)
3. **Scan via Playwright MCP** — hydrate each URL, extract postings (title, company, location, posted_date, description snippet, URL)
4. **Dedup** — check `tracking/known-companies.json` (company + role-bucket key); skip if seen in last 30 days
5. **Score** — apply scoring model; tag matched service(s)
6. **Enrich hot leads** — company career page, Google news, LinkedIn company page (Playwright)
7. **Draft outreach** — per-service templates in `templates/emails/`; render into `templates/drafts/{date}/{slug}.md`
8. **File leads** — create `leads/active/{NN}-{company-slug}.md` for HOT leads
9. **Update tracking** — known-companies.json, lead-log.md
10. **Append lessons-learned.md** — keywords that worked, queries that flopped, new exclusions to consider

## Lead File Convention

Each HOT lead gets `leads/active/{NN}-{company-slug}.md`:

```markdown
# {Company Name} — {Primary Service Match}

- **Score:** 5.2
- **Scope:** local_60mi_irvine | remote_us
- **Matched services:** my-it, my-security
- **Role signaling need:** "IT Manager" (sole IT)
- **Posted:** 2026-04-15
- **Posting URL:** {direct URL, never a search URL}
- **Company URL:** {...}
- **HQ:** {City, State}
- **Est. size:** {employee count if discoverable}
- **Contact (best guess):** {name if discoverable, else leave blank}

## Why they fit
- {1-3 bullets grounded in JD excerpts + service pain_signals}

## JD excerpt
> {relevant snippet}

## Outreach draft
See `templates/drafts/{date}/{slug}.md`.

## Status
- [ ] Reviewed by rjain
- [ ] Sent
- [ ] Reply received
- [ ] Meeting booked
- [ ] Closed won / lost
```

## Self-Improving Loop (MANDATORY)

**READ at start of every run:** `tracking/lessons-learned.md`

Apply active lessons before scanning. Categories:
- Queries that surface good leads (prioritize)
- Queries that waste time (deprioritize)
- False-positive patterns to auto-reject
- Strong-signal patterns worth promoting to `services.yml`

**WRITE at end of every run:** append new entries with date + why.

Format: `- YYYY-MM-DD: <lesson> — <why/context>`

Never delete lessons. Mark obsolete ones with `[OBSOLETE]`.

## Token / Rate-Limit Discipline

- Per-scan cap: `max_queries_per_run: 60` (see portals.yml)
- Per-request jitter: 2-5s between page loads
- User-agent rotation: on
- Respect robots.txt: on
- If a portal returns a 429 or captcha-wall: back off that portal for the rest of the run, log, move on
- NEVER scrape LinkedIn with authenticated cookies — public pages only

## Technology Stack

- **Scraping:** Playwright MCP (`.mcp.json`)
- **Language:** Python 3.11+ for scripts (scan, score) and PowerShell for email (reuse hiring-repo pattern)
- **LLM scoring:** Claude via Anthropic SDK (Sonnet 4.6 for per-lead scoring; Opus 4.7 only for exec-brief summaries)
- **Email:** Microsoft Graph via client-credentials app (same app registration as `technijian-admin-job-postings`)
- **Persistence:** YAML config, JSON tracking, Markdown artifacts

## Git Convention

- Commit after every pipeline run with lead count + top services hit in the message
- Co-Author trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- Never commit `templates/drafts/` with sensitive contact data — drafts are gitignored

## Adjacent Repos (reference, don't modify)

- `D:\vscode\callie-job\-callie-job\` — original (find-jobs-for-a-candidate) pattern
- `D:\vscode\technijian-admin-job-postings\job-postings\Scripts\_Config.ps1` — M365 Graph auth pattern
- `D:\vscode\technijian-admin-job-postings\job-postings\Scripts\6-SendEmail.ps1` — dedup-safe sendMail implementation
- `D:\vscode\tech-branding\Services\` — the PDFs that seeded `config/services.yml`
- `D:\obsidian\tech-leads\tech-leads\` — Obsidian vault (auto-ingested via UserPromptSubmit hook, auto-appended via Stop hook)
