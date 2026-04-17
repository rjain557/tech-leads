# Outreach playbook

How Technijian contacts companies surfaced by the lead-gen pipeline, and why.

## TL;DR

- **Plain-text, JD-specific, three-touch email sequence.** No brochures, no attachments, no resume-style docs, no logos, no HTML.
- **Specificity (quoting the JD) is the single biggest lever on cold B2B reply rate** — bigger than copy quality, bigger than design.
- Brochures and service PDFs are closers, not openers. They go out after a reply, never in touch 1.

## The three-touch cadence

| Touch | Day | Purpose |
|-------|-----|---------|
| 1 | 0 | Quote the JD. Offer reframe. Ask for a reply. No link, no attachment. |
| 2 | 4 | One specific inline observation — a concrete pitfall, number, or reframe tied to the role. No link, no attachment. |
| 3 | 10 | Open-ended question: "did you fill the role?" |

After touch 3 with no reply → mark cold, do not re-queue for 90 days.

Case studies are **not part of the email sequence**. The goal of the email funnel is a reply → meeting. Case studies belong later in the funnel — when a prospect replies asking for proof, during the meeting itself (referenced verbally, not as a deck), and in the proposal phase when someone at the buyer's company is reviewing the decision and needs receipts. See "Where case studies actually fit" below.

## Why brochures underperform for cold B2B

- They pattern-match to "mass mailer" and get filtered mentally before the buyer reads a word
- HTML + images + logos lower deliverability for unfamiliar senders
- They say "I want you to know about us," not "I noticed something specific about you"
- The buyer didn't ask for a brochure — sending one unasked is the opposite of peer-to-peer

Brochures belong in the **nurture** phase, after a reply. Reserve them for:
- Decision-maker sharing internally
- Follow-ups where the buyer asked "can you send more info?"
- Proposal attachments

## Where case studies fit (in this pipeline: nowhere)

- **Email sequence:** no. Specificity of the JD quote does the work, not case studies.
- **On-request reply:** no — rjain replies personally and speaks to similar work from memory.
- **Discovery meeting:** no — rjain references similar work verbally on the call.
- **Proposal:** no — rjain writes the proposal and speaks to peer work directly.

Written case studies on technijian.com/case-studies remain useful for SEO and for the "do these people have receipts?" pre-meeting skim buyers do, but that's a marketing-site concern on a different track from this pipeline. The pipeline itself never produces, attaches, or links to one.

No case-study library needs to exist for this pipeline to run end-to-end.

## Why resume-style docs underperform

Technijian's frame in cold outreach is **peer-to-peer vendor → ops leader**. Resume-style docs cast Technijian as an applicant answering the job posting, which is:
- Confusing (the buyer is hiring a human, not a vendor)
- Off-price (it invites comparison to an employee's salary, not to the service's value)
- Easy to dismiss (the buyer has an ATS for this; your doc isn't in it)

## How Claude drafts each lead

The [draft-outreach skill](../.claude/skills/draft-outreach/SKILL.md) handles the render:

1. Load the lead packet (company, role, JD quote, matched service, contact)
2. Load [_base.md](../templates/emails/_base.md) + the per-service template
3. Resolve placeholders; flag any that can't be resolved
4. Render three touches into [templates/drafts/{YYYY-MM-DD}/{slug}.md](../templates/drafts/) + `.json`
5. Human review before send — `outreach.mode: draft_only` per [targeting.yml](../config/targeting.yml)

## Sending

Send mode is **draft-only** by default. To enable auto-send, rjain must:
1. Flip `outreach.mode` to `auto_send` in [config/targeting.yml](../config/targeting.yml)
2. Approve the first batch in-conversation
3. Respect the 50/day hard cap

Sending implementation reuses the M365 Graph pattern from the `technijian-admin-job-postings` repo (client-credentials, `sendMail` endpoint, dedup against Sent Items).

## Measuring

Track these in [tracking/lead-log.md](../tracking/lead-log.md):
- Sent date per touch
- Reply date (if any)
- Reply sentiment (positive / neutral / negative / out-of-office)
- Meeting booked (yes/no)

After ~30 days of volume: attribute reply rate by service. Services with < 3% reply rate after 50 sends get their template rewritten. Services above 8% get the template studied and applied to the weakest ones.

## Reference material on the approach

- [_base.md](../templates/emails/_base.md) — structural rules
- [per-service templates](../templates/emails/) — one per service slug in [services.yml](../config/services.yml)
- [draft-outreach skill](../.claude/skills/draft-outreach/SKILL.md) — render instructions for Claude
