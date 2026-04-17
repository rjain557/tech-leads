"""
build_outreach.py -- Stage 3 of the pipeline: render three-touch outreach drafts.

Runs AFTER qualify_leads.py has trimmed leads/active/ to only qualified leads.
For each lead, calls Sonnet 4.6 with the lead packet + per-service markdown
template and produces draft emails (touch 1 / touch 2 / touch 3) rendered
with placeholders resolved (picked {{jd_quote}}, company name, role, etc.).

Writes one pair per lead:
  templates/drafts/{YYYY-MM-DD}/{slug}.md   -- human-readable draft (all 3 touches)
  templates/drafts/{YYYY-MM-DD}/{slug}.json -- metadata + unresolved placeholders

outreach.mode: draft_only (config/targeting.yml) -- NEVER sends from here.
Runs in the weekly pipeline via Run-Weekly.ps1.

Usage:
    python scripts/build_outreach.py                 # all leads/active/*.md
    python scripts/build_outreach.py --limit 2       # first N (testing)
    python scripts/build_outreach.py --dry-run       # no API, writes stubbed drafts
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Force UTF-8 stdout so CJK / fullwidth-paren company names don't crash cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO = Path(__file__).resolve().parent.parent
LEADS_ACTIVE = REPO / "leads" / "active"
TEMPLATES = REPO / "templates" / "emails"
DRAFTS_ROOT = REPO / "templates" / "drafts"
SECRETS_FILE = REPO / "scripts" / "secrets.json"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"

SIGNATURE = """-- Rajiv Jain
Technijian | Irvine, CA
rjain@technijian.com | 949.379.8500"""


def load_api_key() -> str | None:
    if not SECRETS_FILE.exists():
        return None
    try:
        d = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        k = d.get("anthropicApiKey")
        return k if k and isinstance(k, str) and k.strip() else None
    except Exception:
        return None


def parse_lead(path: Path) -> dict:
    """Pull header fields + JD excerpt out of a lead .md."""
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^-\s+\*\*([^:*]+):\*\*\s+(.*)$", line)
        if m:
            fields[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
    # Company from H1 — scan_jobs.py writes "# {company} — {primary_service}".
    # Must anchor the capture to a single line (use non-newline class) and strip
    # the trailing " — {service}" suffix. Previous `.+?` let the regex span into
    # "- **Score:**" on the next line, capturing "{company} — {service}" as the
    # company value.
    h1 = re.search(r"^#[^\S\n]+([^\n]+?)[^\S\n]*$", text, re.MULTILINE)
    if h1:
        raw = h1.group(1).strip()
        # strip trailing " — service-slug" (em/en dash, or ascii -- / -)
        raw = re.sub(r"\s+[\u2014\u2013\-]{1,2}\s+\S+$", "", raw).strip()
        fields["company"] = raw
    # JD excerpt (first 1200 chars scan_jobs saves)
    jd = re.search(r"##\s+JD excerpt\s*\n\s*>\s*(.+?)(?:\n##|\Z)", text, re.DOTALL)
    if jd:
        fields["jd_excerpt"] = jd.group(1).strip()
    # Rationale (qualifier block)
    rat = re.search(r"\n>\s+(.+?)(?:\n##|\Z)", text, re.DOTALL)
    if rat and "jd_excerpt" not in fields:
        pass  # keep order stable; qualifier rationale already a `>` after `## Qualification`
    return fields


def primary_service(lead: dict) -> str:
    s = (lead.get("matched_services") or "").split(",")[0].strip()
    return s or "my-it"


def call_anthropic(api_key: str, prompt: str, retries: int = 3) -> str:
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1600,
        "system": "You render cold B2B outreach email drafts. Output ONLY a JSON object with keys: subject, touch1, touch2, touch3, jd_quote_picked, unresolved_placeholders. No prose. No code fences.",
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    delay = 2.0
    for attempt in range(retries):
        try:
            req = Request(ANTHROPIC_URL, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0]["text"]
            return ""
        except HTTPError as e:
            status = e.code
            if status in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay *= 2
                continue
            raise
        except URLError:
            if attempt < retries - 1:
                time.sleep(delay); delay *= 2
                continue
            raise
    return ""


PROMPT_TEMPLATE = """Render a three-touch cold-outreach sequence for this lead using the per-service template below.

LEAD
----
Company: {company}
Role posted: {role}
Location: {location}
Primary service match: {service}
Matched services (all): {all_services}

JD excerpt (pick a 6-12 word {{jd_quote}} from this that signals the specific pain the role was opened to solve):
{jd_excerpt}

PER-SERVICE TEMPLATE (follow structure; resolve placeholders; keep voice)
---------
{template}

RULES
-----
- Touch 1 body must be <=120 words. No links. No attachments.
- Touch 2 body must be 60-80 words. No links. One specific inline observation.
- Touch 3 body must be <=40 words. No links.
- Resolve {{company}}={company}. {{role}}={role}. {{signature}} is appended separately - omit it from the body you return.
- {{contact_first_name}} unknown -> use "team".
- {{jd_quote}} -> quote 6-12 words verbatim from the JD excerpt that prove you read the posting.
- Rewrite mechanical-sounding lines so it reads like a human had a thought worth sharing.
- Pick the SINGLE most specific subject variant from the template - the one that quotes the role or a pain.

OUTPUT (JSON only):
{{
  "subject": "...",
  "touch1": "...",
  "touch2": "...",
  "touch3": "...",
  "jd_quote_picked": "...",
  "unresolved_placeholders": ["..."]
}}"""


def render_draft(api_key: str, lead: dict, template_text: str, dry: bool) -> dict:
    if dry:
        return {
            "subject": f"[DRY] Re: your {lead.get('role_signaling_need','role')} posting",
            "touch1": "[DRY RUN - no API call made]",
            "touch2": "[DRY RUN]",
            "touch3": "[DRY RUN]",
            "jd_quote_picked": "",
            "unresolved_placeholders": [],
        }
    prompt = PROMPT_TEMPLATE.format(
        company=lead.get("company", "(unknown)"),
        role=lead.get("role_signaling_need", "(unknown role)"),
        location=lead.get("location", ""),
        service=primary_service(lead),
        all_services=lead.get("matched_services", ""),
        jd_excerpt=lead.get("jd_excerpt", "(no JD excerpt on file)")[:1800],
        template=template_text[:6000],
    )
    raw = call_anthropic(api_key, prompt)
    # Strip code fences defensively
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"subject": "PARSE_ERROR", "touch1": raw[:2000], "touch2": "", "touch3": "", "jd_quote_picked": "", "unresolved_placeholders": ["parse_error"]}


def write_draft(lead: dict, slug: str, rendered: dict, date_dir: Path) -> None:
    md = f"""# {lead.get('company','(unknown)')} -- Outreach draft ({primary_service(lead)})

**Lead:** {lead.get('role_signaling_need','')} at {lead.get('company','')}
**Score:** {lead.get('score','?')} | **Confidence:** {lead.get('confidence','?')} | **Likely buyer:** {lead.get('likely_buyer','?')}
**Posting:** {lead.get('posting_url','')}

---

## Touch 1 -- Day 0
**Subject:** {rendered.get('subject','')}

{rendered.get('touch1','')}

{SIGNATURE}

---

## Touch 2 -- Day 4
**Subject:** Re: {rendered.get('subject','')}

{rendered.get('touch2','')}

{SIGNATURE}

---

## Touch 3 -- Day 10
**Subject:** Re: {rendered.get('subject','')}

{rendered.get('touch3','')}

{SIGNATURE}
"""
    (date_dir / f"{slug}.md").write_text(md, encoding="utf-8")
    meta = {
        "company": lead.get("company"),
        "slug": slug,
        "matched_service": primary_service(lead),
        "role": lead.get("role_signaling_need"),
        "score": lead.get("score"),
        "confidence": lead.get("confidence"),
        "likely_buyer": lead.get("likely_buyer"),
        "posting_url": lead.get("posting_url"),
        "jd_quote_picked": rendered.get("jd_quote_picked"),
        "unresolved_placeholders": rendered.get("unresolved_placeholders", []),
        "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "draft_pending_review",
    }
    (date_dir / f"{slug}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", type=str, default=None,
                    help="Slug substring to filter leads (e.g. 'bvital' re-renders only bvital-park-city)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not LEADS_ACTIVE.exists():
        print("No leads/active/ directory -- nothing to build.")
        return 0
    leads = sorted(LEADS_ACTIVE.glob("*.md"))
    if args.only:
        needle = args.only.lower()
        leads = [p for p in leads if needle in p.stem.lower()]
    if args.limit:
        leads = leads[: args.limit]
    if not leads:
        print("No qualified leads in leads/active/.")
        return 0

    api_key = None if args.dry_run else load_api_key()
    if not args.dry_run and not api_key:
        print("ERROR: anthropicApiKey not in secrets.json; cannot render drafts. Use --dry-run for stubs.", file=sys.stderr)
        return 2

    date_dir = DRAFTS_ROOT / datetime.now().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    built = skipped = 0
    for lp in leads:
        lead = parse_lead(lp)
        svc = primary_service(lead)
        tpl_path = TEMPLATES / f"{svc}.md"
        if not tpl_path.exists():
            print(f"  [skip] no template for {svc} -- {lp.name}")
            skipped += 1
            continue
        template_text = tpl_path.read_text(encoding="utf-8")
        slug = lp.stem.split("-", 1)[-1]
        try:
            rendered = render_draft(api_key, lead, template_text, args.dry_run)
            write_draft(lead, slug, rendered, date_dir)
            built += 1
            print(f"  [ok] {slug} -- {svc}")
        except Exception as e:
            print(f"  [err] {slug}: {e}", file=sys.stderr)
            skipped += 1

    print(f"\nBuilt {built} drafts, skipped {skipped}. Output: {date_dir}")
    return 0 if built else 1


if __name__ == "__main__":
    sys.exit(main())
