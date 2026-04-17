---
name: draft-reply
description: Draft responses to inbound replies on our cold outreach threads. Invoke when the user says "draft replies for today", "respond to {company}", or after Check-Replies.ps1 has logged new replies. Reads from tracking/replies/{date}.md, produces drafts into templates/replies/{date}/{slug}.md. Human review before send — `outreach.mode: draft_only` applies to replies too.
---

# draft-reply

Draft responses to inbound replies captured by [scripts/Check-Replies.ps1](../../../scripts/Check-Replies.ps1). This is the companion to [draft-outreach](../draft-outreach/SKILL.md) — that one handles cold touches, this one handles warm responses to humans who actually replied.

## When to invoke

- User says "draft replies for today" / "draft today's replies" / "respond to {company}"
- Right after a Check-Replies run flagged new pending replies
- User opens a specific `tracking/replies/{YYYY-MM-DD}.md` entry and asks for a draft

Do NOT invoke for entries flagged `HANDLED`, `AUTO`, or `UNSUBSCRIBE`.

## Input

For each pending reply, you get:
- `from` — sender email address
- `subject` — reply subject line
- `received` — timestamp
- `sentiment` — one of: positive / negative / neutral / curious / unsubscribe
- `conversationId` — Graph thread id
- `originalTo` — address we sent our outreach to
- `bodyPreview` — short snippet of the reply
- `matched_service` (optional) — if the original lead packet is findable, join against [templates/drafts/](../../../templates/drafts/)

If `bodyPreview` is truncated (Graph caps ~255 chars) and you need the full reply body, ask the user to paste it in — do not invent context.

## How to draft per sentiment

**positive:** they're interested. Respond within hours. Confirm, propose a concrete time ("tomorrow 10am or Thu 2pm?"), do not re-pitch.

**curious:** they want to know who you are / how you found them. Respond honestly (1-2 sentences): "we run a lead-gen pipeline that flags companies hiring for roles Technijian services overlap with — I saw your {role} posting and had a thought worth sharing. Happy to explain on a 15-min call or walk you through it by email — your call."

**neutral:** acknowledged-but-no-clear-yes. One short follow-up that names the next step ("Want me to send a one-pager, or worth a 15-min call?") — offer, don't pressure.

**negative:** they're polite-but-no. Thank them, leave the door open in 90 days. "Thanks for the quick reply — I'll circle back in a quarter in case anything changes." Then add a note to [tracking/known-companies.json](../../../tracking/known-companies.json) to suppress for 90 days.

**unsubscribe:** do NOT draft. Flag for the user to manually remove from all future lists and respond with a one-line acknowledgement. Add to a `tracking/suppress.json` list (create if missing).

## Output

Write to `templates/replies/{YYYY-MM-DD}/{company-slug}.md` (gitignored). One file per reply.

```markdown
# Reply to {from} — {subject}

- **Sentiment:** {sentiment}
- **Received:** {received}
- **Matched service:** {matched_service or "unknown"}
- **ConversationId:** `{cid}`

## Original reply (snippet)
> {bodyPreview}

## Draft response

**Subject:** Re: {original subject stripped of Re:/Fwd:}

{body — plain text, ≤ 80 words for positive/neutral/curious, ≤ 40 words for negative}

— Rajiv
```

Also append a one-liner to `tracking/replies/{date}.md` under each entry: `**Draft ready:** templates/replies/{date}/{slug}.md`

## Principles

- **Answer the question they asked.** If they asked "who are you?", don't answer with a pitch.
- **Match their energy.** Short reply → short response. Questions → answers, not deflection.
- **Name a concrete next step.** Time, format, or tradeoff — not "happy to chat further."
- **Never re-pitch to a negative.** It burns the 90-day re-engagement option.
- **Never promise what Technijian can't do.** If the sentiment is "sure, tell me more" but you don't know the matched service's current capacity, flag it in the draft with `[CONFIRM WITH RJAIN]`.

## What this skill does NOT do

- Does not send — replies go out manually per `outreach.mode: draft_only`
- Does not mark messages read in Outlook — the Check-Replies script is read-only and this skill is too
- Does not modify [tracking/replies/_seen.json](../../../tracking/replies/_seen.json) — that's the script's state
- Does not touch [templates/drafts/](../../../templates/drafts/) (that's outbound cold) — only [templates/replies/](../../../templates/replies/) (inbound response)

## Related

- [Check-Replies.ps1](../../../scripts/Check-Replies.ps1) — the daily monitor that feeds this skill
- [draft-outreach SKILL.md](../draft-outreach/SKILL.md) — outbound cold sibling
- [services.yml](../../../config/services.yml) — look up matched_service for context on pitch/pain