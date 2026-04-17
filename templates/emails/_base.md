# Base outreach template — read first

This is the canonical structure every per-service template inherits. The accompanying skill at [.claude/skills/draft-outreach/SKILL.md](../../.claude/skills/draft-outreach/SKILL.md) tells Claude how to render a draft per lead.

## Why cold B2B rules differ from brochures

Technijian's signal is "this company is hiring for a role we could replace or augment." That frame is **peer-to-peer vendor → ops leader**, not applicant → hiring manager and not vendor → unqualified prospect. Brochures and resume-style attachments both misread the room:

- Brochures trigger the spam-filter mental model ("mass mailer"). Reply rates crater.
- Resume-style docs miscast Technijian as an applicant instead of a solution.
- Logos, HTML tables, and marketing imagery drop deliverability (Gmail/Outlook both weight plain text higher for unfamiliar senders).

What actually moves reply rate on cold B2B, in order of impact:

1. **Specificity** — quoting the JD proves a human read it. Biggest single lever.
2. **Brevity** — under ~120 words. Anything longer reads like a pitch.
3. **Relevance of the offer** — tied to the exact pain the role is being hired to solve.
4. **Single soft CTA** — "worth a reply?" beats "book a 30-min demo."
5. **Plain text + human sender** — rjain@technijian.com from a person, not marketing@.

## Cadence (three touches, total)

| Touch | Day | Purpose | Format |
|-------|-----|---------|--------|
| 1 | 0 | First touch, quote the JD | Plain text, ≤120 words, no attachment |
| 2 | 4 | One specific inline observation — a concrete pitfall, number, or reframe tied to the role | Plain text, ~60–80 words, no links, no attachments |
| 3 | 10 | Open-ended question | Plain text, ~40 words, no links |

If no reply after touch 3 → mark cold, do not re-queue for 90 days. Log under `tracking/known-companies.json` with `last_contacted`.

## Universal placeholders

Every service template uses these. The skill resolves them from the lead packet:

- `{{contact_first_name}}` — best-guess contact first name; fallback `"team"` if unknown
- `{{company}}` — company display name
- `{{role}}` — the exact job title they posted
- `{{jd_quote}}` — 6–12-word verbatim excerpt from the JD that signals the pain
- `{{pain_ref}}` — Technijian's framing of that pain (service-specific, see each template)

## Universal DO

- Write like the sender just read the JD and had a thought worth sharing
- One idea per paragraph; one sentence per paragraph where possible
- Lowercase, conversational, em dashes OK
- Put the sender signature in 3 lines, no logo, no banner

## Universal DO NOT

- No "I hope this email finds you well", "Quick question", "Touching base", "Circling back"
- No brochures, PDFs, decks, logos, or images
- No links at all in touches 1–3 (we don't want any link at this stage — deliverability + keeps the frame conversational)
- No mention of "AI" in the opener unless the service itself is My AI / My AI Lead Gen
- No asking for 30 minutes. Ask for a reply, or 15 min max
- No HTML. Markdown drafts render to plain text at send time

## Signature (canonical)

```
— Rajiv Jain
Technijian · Irvine, CA
rjain@technijian.com · 949.379.8500
```

## Per-service templates

- [my-it.md](my-it.md)
- [my-ai.md](my-ai.md)
- [my-ai-lead-gen.md](my-ai-lead-gen.md)
- [my-cloud.md](my-cloud.md)
- [my-compliance-hipaa.md](my-compliance-hipaa.md)
- [my-compliance-cmmc.md](my-compliance-cmmc.md)
- [my-continuity.md](my-continuity.md)
- [my-dev.md](my-dev.md)
- [my-office.md](my-office.md)
- [my-seo.md](my-seo.md)
- [my-security.md](my-security.md)
