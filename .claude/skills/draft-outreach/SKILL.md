---
name: draft-outreach
description: Draft the three-touch email sequence for a HOT lead in the Technijian lead-gen pipeline. Invoke when a lead has been scored HOT and needs files written to templates/drafts/{YYYY-MM-DD}/{company-slug}.md + .json. Produces plain-text, JD-specific, peer-to-peer cold outreach — never brochures, attachments, or logos.
---

# draft-outreach

Draft the three-touch cold outreach sequence for a HOT lead in the Technijian lead-gen pipeline.

## When to invoke

- A lead just scored ≥ 4.0 in the scoring pipeline (see [CLAUDE.md](../../../CLAUDE.md))
- User says "draft outreach for {company}" or "write the email for lead {NN}"
- Batch re-draft pass after `config/targeting.yml` or a per-service template is updated

Do NOT invoke for WARM leads (2.5–4.0). Those are logged only, not drafted.

## Before starting — gather the lead packet

You need these fields. If any are missing, ask once, then stop.

- `company` — display name
- `company_slug` — kebab-case
- `contact_first_name` — best guess; `"team"` if unknown
- `role` — exact posted job title
- `jd_quote` — 6–12-word verbatim excerpt from the JD that signals the pain
- `matched_service` — slug from [config/services.yml](../../../config/services.yml)
- `scope` — `local_60mi_irvine` or `remote_us`
- `posted_date` — recency shapes urgency framing

## How to draft

1. **Load the per-service template** at `templates/emails/{matched_service}.md`. These inherit from [_base.md](../../../templates/emails/_base.md) — read `_base.md` first.
2. **Resolve every placeholder.** No `{{...}}` left in output unless you've flagged it in the JSON metadata as needing review.
3. **Render three touches** with these absolute caps:
   - Touch 1 (day 0): ≤ 120 words, plain text, **no links**
   - Touch 2 (day 4): ~60–80 words, plain text, one specific inline observation (concrete pitfall, number, or reframe), **no links**
   - Touch 3 (day 10): ~40 words, no links
4. **Subject lines:** pick the single most specific of the three variants in the service template — the one that quotes the role or a pain, never a generic "touching base."
5. **Rewrite mechanically-generated lines.** If a sentence from the template reads like a template (odd seams, repeated nouns), rewrite it so it reads like someone who just read the JD had a thought.

## Output files

Write TWO files per lead, per the convention in [CLAUDE.md](../../../CLAUDE.md):

### `templates/drafts/{YYYY-MM-DD}/{company-slug}.md`

```markdown
# {company} — Outreach draft ({matched_service})

## Touch 1 — Send date: {posted_date + 1 business day}
**Subject:** {chosen subject}

{body}

---

## Touch 2 — Send date: {touch 1 date + 4}
**Subject:** Re: {touch 1 subject}

{body}

---

## Touch 3 — Send date: {touch 1 date + 10}
**Subject:** Re: {touch 1 subject}

{body}
```

### `templates/drafts/{YYYY-MM-DD}/{company-slug}.json`

```json
{
  "company": "...",
  "company_slug": "...",
  "matched_service": "my-xx",
  "score": 5.2,
  "contact_first_name": "...",
  "contact_email": "...|null",
  "role": "...",
  "jd_quote": "...",
  "posted_date": "2026-04-15",
  "scope": "local_60mi_irvine",
  "touches": [
    {"n": 1, "scheduled_send": "2026-04-18", "subject": "...", "word_count": 117},
    {"n": 2, "scheduled_send": "2026-04-22", "subject": "...", "word_count": 81},
    {"n": 3, "scheduled_send": "2026-04-28", "subject": "...", "word_count": 38}
  ],
  "placeholders_unresolved": [],
  "status": "draft_pending_review"
}
```

## Principles (deviate only with cause)

- **Write like a peer who just read the JD.** Not like a vendor, not like an applicant.
- **Specificity > cleverness.** A 6-word JD quote outperforms a witty opener every time.
- **One idea per paragraph. One CTA per email.** More than that reads like a pitch deck.
- **Plain text only.** No HTML, no logos, no attachments. Markdown renders to plain at send time.
- **Say "worth a reply" not "book a 30-minute demo."** Soft CTAs win cold reply rate.
- **Never AI-wash.** Do not mention AI / LLM / agents in the opener unless the matched service is My AI or My AI Lead Gen.
- **Never use these phrases:** "I hope this finds you well", "Quick question", "Touching base", "Circling back", "per my last email."

## Proactive flags (raise without being asked)

- Touch 1 body > 120 words → trim
- Touch 2 body > 80 words or contains a link → trim / strip the link
- Any touch contains a link or attachment → strip; the sequence is link-free by design
- Any placeholder unresolved → list in JSON `placeholders_unresolved`
- `contact_first_name` is still `"team"` → suggest enrichment before send
- JD quote reads generic (e.g. "strong work ethic") → pick a sharper one; the JD quote IS the personalization

## What this skill does NOT do

- Does not send email. Drafts are `draft_only` per [config/targeting.yml](../../../config/targeting.yml). Sending is manual.
- Does not enrich leads. If contact info is missing, flag and stop — do not guess.
- Does not handle WARM or cold leads. HOT only.
- Does not modify `templates/emails/*.md` — those are edited by hand, not by this skill.

## Related files

- [templates/emails/_base.md](../../../templates/emails/_base.md) — canonical structure
- [templates/emails/my-*.md](../../../templates/emails/) — per-service variants
- [config/services.yml](../../../config/services.yml) — pain signals, buyer titles
- [config/targeting.yml](../../../config/targeting.yml) — outreach mode, rate limits