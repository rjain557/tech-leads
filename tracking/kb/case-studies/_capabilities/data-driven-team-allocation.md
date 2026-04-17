# Data-Driven Team Allocation

- **Capability:** Dev + Operations Intelligence
- **Applies to:** Any services firm with 3+ specialists and per-engagement billing

## What was built

A Python analyzer (`seo_team_skills_analyzer.py`) that pulls 30 days of billing-level time entries from the Client Portal API (stored-procedure exec), tags each entry with a skill category (technical SEO, on-page, keyword research, WordPress, video, outreach, reporting), and emits a `seo_team_skills.md` document that answers, for every lowlight type: **first choice, second choice, third choice** specialist to assign.

## How it works

- Pulls time entries by UserID via `stp_xml_TicketDetail_TimeSheet_Detail_Get`.
- Classifies each ticket into one of ~10 SEO skill buckets via keyword rules on   the title/notes.
- Aggregates hours per person per skill; builds an assignment decision matrix.
- Flags overload (> 40h / week sustained) so the planner raises it instead of   silently piling on.

## Outcomes

- Assignment decisions for weekly reviews are data-backed, not tribal.
- The artifact refreshes every 4–6 weeks — the team's actual work (not their job   titles) drives who gets what.
- Overload is visible in writing before it becomes a burnout or delivery problem.

## Outreach-ready summary

We read our own time-tracking data the way a CFO reads an income statement. Every 4-6 weeks the skill matrix refreshes — each specialist's real hours by category drive assignment decisions. It's why our SEO delivery stays consistent as team composition shifts.
