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

## Lessons learned — 2026-04-17 first-batch mistakes (MANDATORY reading before pipeline changes)

Every mistake in this list was made live today when pushing the first batch of cold-outreach drafts. Each has a fix baked into the current code. Do not regress them.

1. **Subject lines: Title Case, not lowercase.** "the IT Manager posting" reads sloppy for cold first-impression email. Use "Saw Your IT Manager Search" / "Question About the M365 Role at {Company}". Enforced in [build_outreach.py](scripts/build_outreach.py) `PROMPT_TEMPLATE` SUBJECT LINES section.

2. **Body must be 3–4 short paragraphs, not one wall of text.** LLM default was "one paragraph, 100 words". Must be 1–2 sentences per paragraph, separated by blank lines. Enforced in prompt + [Put-DraftsInOutlook.ps1](scripts/Put-DraftsInOutlook.ps1) `Convert-BodyToHtml` has heuristic re-split at sentence boundaries if the LLM returns one big paragraph.

3. **HTML body with real signature — NEVER plain text.** Plain text + the ASCII "-- Rajiv Jain / Technijian | Irvine, CA" block looks amateur. Real signature is at [templates/signature.html](templates/signature.html) (extracted from `/mailFolders/SentItems/messages`). Body: Aptos 12pt, line-height 1.55, 16px paragraph spacing, 24px div spacer before signature table. No exceptions.

4. **Match Ravi's actual voice — sample his Sent folder first.** [scripts/Sample-Voice.ps1](scripts/Sample-Voice.ps1) pulls 40 recent sent emails into `Logs/voice-samples/`. [templates/voice-profile.md](templates/voice-profile.md) distills the patterns. The prompt embeds it. Banned-phrase list enforced: no "fractional-MSP run rate", "$95K + benefits + coverage gaps", "covers the 24/7 layer", "Not arguing against the hire — sometimes it's exactly right", "the part that caught me", em-dashes. These were the AI-generated tells that made the first batch obvious.

5. **Contact enrichment BEFORE draft generation.** Pushing drafts with empty `To:` and a CONTACT TODO research block was a band-aid that made the user rightly ask "how am I supposed to send these?" [scripts/enrich_contacts.py](scripts/enrich_contacts.py) runs Stage 2.5 in [Run-Weekly.ps1](scripts/Run-Weekly.ps1), resolves contacts via Hunter.io, writes to lead files. `contact_first_name` flows into the prompt so drafts open with "Robyn," not "Hi team,".

6. **Default cadence: ONE touch per lead, not three.** User pushback: "You think the lead is going to like get 3 emails from me?" 3-touch auto-cadence reads as spam to the recipient. [Put-DraftsInOutlook.ps1](scripts/Put-DraftsInOutlook.ps1) now defaults `-Touch "1"`. Touches 2 and 3 still render locally for manual push on specific leads that go cold — never auto-pushed.

7. **Mention the booking link in the body.** Signature has a "Book a Meeting" button; the body must reference it ("there's a calendar link in my signature to grab some time"). Otherwise readers scan body → miss the button → reply with "what's the next step?"

8. **Apollo is the wrong enrichment vendor.** Plan tier gates `mixed_people/search` (403 API_INACCESSIBLE) and `mixed_companies/search` runs out of credits. **Hunter.io** is the vendor. `/v2/domain-search?company={name}` resolves domain + returns top executives with verified emails + titles + seniority — exactly what we need. Key in [keys/hunter.md](file:///C:/Users/rjain.TECHNIJIAN/OneDrive%20-%20Technijian,%20Inc/Documents/VSCODE/keys/hunter.md), loaded from `scripts/secrets.json → hunterApiKey`.

9. **BatchData is the wrong tool entirely.** Address-based skip-trace returns property owners — wrong signal for B2B decision-maker outreach. Confirmed by reading `/d/vscode/finance-leadgen/sources/apollo_enrich.py` — finance-leadgen's own docs flagged the gap but never filled it.

10. **Proofread every draft after pushing — not one sample.** [scripts/Proofread-All.ps1](scripts/Proofread-All.ps1) iterates all pushed drafts via Graph, strips HTML, counts paragraphs + words, scans for banned phrases, verifies booking-link mention. Run after every `Put-DraftsInOutlook` execution before declaring a batch ready for review.

11. **Greeting and first sentence go on the SAME paragraph.** Some LLM outputs put "Elizabeth" alone, blank line, then the body. Reads robotic. Enforce: "Robyn, saw the IT Systems Administrator posting..." — comma inline, no newline break after the name.

12. **HTML email draft + Graph API needs `Mail.ReadWrite` permission.** The existing HiringPipeline-Automation app registration has it (verified — 27/27 drafts pushed without 403). If this ever changes, `Put-DraftsInOutlook.ps1` fails with a clear 403 message pointing at the permission.

## Outlook drafts are the review surface (MANDATORY)

**Every email the pipeline generates ends up in rjain's Outlook Drafts folder.** Not in local `templates/drafts/{date}/` for rjain to open separately — in Outlook, where he proofreads and sends from.

- Outbound outreach drafts (touches 1/2/3): `scripts/Put-DraftsInOutlook.ps1` runs at the end of the weekly chain. All three touches are pushed per lead with categories `tech-leads` + `outreach-touch-{N}` so they can be filtered.
- Inbound reply drafts (responses to prospect replies): `scripts/Put-ReplyInOutlook.ps1` runs after the `draft-reply` skill renders. Uses Graph `/createReply` so the draft threads into the original conversation.

**Contact enrichment is NOT currently automated.** Apollo free/starter tier rejects the endpoints we need (`mixed_people/search` → 403 API_INACCESSIBLE; `organizations/enrich` → 422 insufficient credits). Until a paid Apollo plan or a scraping-based enrichment is added, every draft pushed to Outlook includes a **CONTACT TODO** research block at the top of the body with:

- Company name, role, likely decision-maker title
- Pre-built LinkedIn people-search URL (`keywords="{buyer}" "{company}"`)
- Pre-built Google search URL (`"{company}" {buyer} email`)
- Original posting URL

Rjain opens the draft in Outlook, clicks the LinkedIn/Google link, finds the contact, pastes the email into To:, deletes the TODO block, sends. Going forward: add contact scraping (Playwright or a paid enrichment API) so drafts arrive with To: populated and the TODO block only appears as a fallback.

## Multi-session write-path convention (MANDATORY)

All pipeline work runs on this workstation. Multiple Claude sessions may be active concurrently — typically a **pipeline session** (scheduled scan / reply check) and a **lead-gen/tuning session** (interactive: iterates on signals, finds new keywords, discovers false-positive patterns, refines scoring + templates). They share the same working tree. The convention below prevents races between them.

**Lead-gen / tuning session** edits (and ONLY these paths):
- `config/services.yml` — add/refine signal_keywords, signal_job_titles, strong_signals, exclusions
- `config/targeting.yml` — tune scoring weights / thresholds
- `tracking/lessons-learned.md` — append lessons learned (date-prefixed)
- `templates/emails/*.md` — refine per-service copy based on reply data

**Pipeline session** (scan / reply check — whether via `Start-ScheduledTask` or manual invocation) writes (and ONLY these paths):
- `leads/active/` — new lead files
- `tracking/known-companies.json` — dedup + scoring history
- `tracking/lead-log.md` — per-run tally
- `tracking/replies/` — inbound reply log (gitignored)
- `templates/drafts/` — outbound draft output (gitignored)
- `templates/replies/` — inbound response drafts (gitignored)

**Overlap is a bug.** If either session needs to write outside its lane, stop and add the lane here first.

`scripts/Run-Weekly.ps1` does `git pull --rebase` before scanning and `git push` after. That exists for remote backup + commit history — not for inter-session sync on this workstation (sessions share the same working tree directly).

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
