# tech-leads

B2B lead-generation pipeline for Technijian. Scans job boards for companies whose hiring activity signals a need for one of Technijian's services, scores each lead, drafts tailored outreach, and delivers a weekly lead packet.

**Inverted Callie pattern:** instead of *"find jobs that fit this candidate"*, we do *"find companies posting jobs that fit our service catalog."*

## Layout

```
config/
  services.yml      — Technijian service catalog (signal titles, keywords, pain signals per service)
  portals.yml       — Job boards + two scan scopes (60mi Irvine, remote US)
  targeting.yml     — Scoring weights, dedup, outreach mode
scripts/
  scan_jobs.py      — Playwright-driven portal scanner
  score_leads.py    — Apply scoring model, tag services
  build_outreach.py — Render per-service email drafts
  send_email.ps1    — M365 Graph sendMail (DRAFT mode by default)
leads/
  active/           — HOT leads — one .md per company
  archived/         — Processed / closed leads
templates/
  emails/           — Per-service email templates (HTML + plain)
  drafts/           — Rendered drafts awaiting rjain review (gitignored)
tracking/
  known-companies.json — dedup + history
  lead-log.md          — human-readable run log
  lessons-learned.md   — self-improving loop
.mcp.json           — Playwright MCP server (+ googleworkspace later for email)
CLAUDE.md           — Pipeline rules
```

## Running

Not yet wired up. See CLAUDE.md for the intended pipeline.

## Outreach mode

**Draft-only by default.** Flip `config/targeting.yml` → `outreach.mode` to `auto_send` only after rjain approves explicitly. See CLAUDE.md.
