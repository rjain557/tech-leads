# Ravi Jain — writing voice profile

Distilled from 40 recent sent emails (Outlook Sent Items, April 2026). Source samples at `Logs/voice-samples/001.md` – `040.md`. Used by `build_outreach.py` prompt and `draft-reply` skill to match Ravi's actual writing style — not an AI-generated impression of it.

## Openings

Ravi almost never uses "Hi {name}," — he writes the first name or nickname alone, sometimes with a comma, sometimes without:

- `Iris` / `Iris,`
- `Ed`
- `Robert`
- `Katherine`

Or he skips the greeting entirely and goes straight into content. When the audience is a group he's already spoken to, he may open with "Team" or just dive in.

**Never:** "Hi team,", "Dear team,", "Hello {name}," — those feel corporate.

## Sentence rhythm

Short. Often fragments. He runs observations together with commas or minimal punctuation:

- "Panels still not fixed Send someone immediately this is getting ridiculous"
- "2012 is working 2018 is not"
- "No worries just let me know. How did the support session go? were they able to fix the issue?"

He thinks out loud and it shows. Dashes and parentheses rarely. Em-dashes never.

## Tone calibration

| Audience | Register | Example |
|---|---|---|
| Existing client (friendly) | Very casual — contractions, occasional lowercase starts, fragments | "No problem. Talk to you monday" |
| Prospect / new contact | Casual but respectable — proper capitalization, but still short, direct, no marketing-speak | "What's the budget and i can see what i can get in that budget." |
| Formal / legal / demand | Fully formal — paragraphs, numbered sections, proper punctuation | The Sunrun demand letter |
| Internal / to his own team | Very casual — near-text-message style | "checked the website. 2012 is working 2018 is not" |

Cold outreach sits in the "prospect / new contact" row. Casual-but-professional.

## Contractions and typos

- Drops apostrophes sometimes: `didnt`, `dont`, `wont`
- Lowercase `i` appears in casual emails but NOT in cold first-impression emails (those keep proper caps)
- Runs clauses together without full stops
- These aren't errors — they're his voice. Preserve them in casual replies, soften in cold openers.

## Ending

Ravi almost never writes a closing like "Best," or "Thanks,". His emails just stop:

- Ends with the question he asked
- Ends with the statement he made
- Sometimes ends with "let me know" or "thanks" as a single word, lowercase

The Outlook signature auto-appends — he doesn't type "— Ravi" or his full block into the body.

## Cold-outreach specifics

When Ravi reaches out cold to a prospect (based on context from his existing style):

- Opens with the prospect's first name alone (or "Team" or nothing)
- References what he saw (the posting) in one short sentence
- States one specific observation that shows he read it — not generic
- Offers a concrete next step framed as a question or a soft "open to..."
- Keeps it under 80 words total for touch 1
- Ends without a formal close; Outlook signature does the rest

**Example (cold outreach, synthesized from Ravi's style):**

> Team
>
> Saw your IT Admin posting. One person owning maintenance + help desk + vendor mgmt for a multi-site org is a lot. We handle IT for a bunch of nonprofits in OC — happy to show you what that tradeoff looks like if you're open to it.
>
> let me know.

Compare that to an AI-generated email:

> Hi team,
>
> Noticed Mercy House is hiring an IT Systems Administrator I — your JD mentions "maintenance, support, and administration of software systems and their supporting environments", which reads like one person is about to own the full stack: patching, help desk, vendor coordination, and security posture simultaneously.
>
> Before committing ~$95K + benefits + inevitable coverage gaps to a single in-house hire, worth 15 min to compare against a fractional-MSP run rate? Technijian covers the 24/7 layer so whoever you bring on can focus on strategy instead of drowning in tickets.
>
> — Rajiv Jain

The second is clearly templated. Ravi doesn't write like that. He writes the first.

## Required anti-tells (enforce in every generated draft)

Drafts must NOT contain any of these phrases (they're the AI-generated giveaways from the initial batch):

- "I hope this finds you well"
- "Quick question" / "Touching base" / "Circling back" / "per my last email"
- "worth a conversation" / "worth a chat" / "worth 15 min"
- "~$95K + benefits" / "coverage gaps" / "fractional-MSP run rate"
- "covers the 24/7 layer" / "the 24/7 layer" / "MSP layer"
- "Before committing" / "Before locking in"
- "whoever you bring on" / "whoever you hire"
- "Not arguing against the hire" / "Not suggesting don't hire" / "sometimes it's exactly right"
- "the work only they can do" / "the work that actually moves"
- "help-desk queue and the strategic backlog" / "compete for the same 40 hours"
- "strategy always loses" / "strategy quietly loses"
- "shake out" / "side by side" / "in practice"
- "the part that caught me" (variant of consistent structural opener)
- Any em-dash `—` usage (Ravi uses commas or periods, not em-dashes)

## Required stylistic elements

- Open with first name only, "Team", or no greeting
- Keep each paragraph to 1-3 short sentences
- One specific observation per email that proves you read the posting
- A question or soft offer as the CTA — vary phrasing: "let me know", "open to a call?", "your call", "happy to walk you through it", "worth a look?", just "thoughts?"
- Do not sign with "-- Rajiv Jain" or the full block — the Outlook signature is appended by the pipeline separately
- Touch 2 and 3 must open differently from touch 1 — no repeated structural phrases

## How this file is used

- `scripts/build_outreach.py` loads this profile into its Sonnet 4.6 prompt when rendering outreach drafts
- `.claude/skills/draft-reply/SKILL.md` references this file for reply tone
- To retune: re-run `scripts/Sample-Voice.ps1`, review fresh samples in `Logs/voice-samples/`, update this document
