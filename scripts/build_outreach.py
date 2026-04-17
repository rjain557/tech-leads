"""
build_outreach.py — Render per-service outreach email drafts for HOT leads.

Iterates leads/active/*.md (where scan_jobs.py files them), picks a template from
templates/emails/{service-slug}.html, renders replacements, writes to
templates/drafts/{YYYY-MM-DD}/{company-slug}.md (+ .json for metadata).

Drafts are NEVER sent from here — send happens via PowerShell Send-Email.ps1
after rjain reviews and explicitly approves. Per config/targeting.yml
outreach.mode (`draft_only` by default).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")


REPO = Path(__file__).resolve().parent.parent
LEADS_ACTIVE = REPO / "leads" / "active"
TEMPLATES = REPO / "templates" / "emails"
DRAFTS_ROOT = REPO / "templates" / "drafts"


def load_lead(path: Path) -> dict:
    """Parse a lead markdown file into a dict of fields."""
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\-\s+\*\*([^:*]+):\*\*\s+(.*)$", line)
        if m:
            fields[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
    return fields


def render_template(svc_slug: str, lead: dict) -> str | None:
    tpl_path = TEMPLATES / f"{svc_slug}.html"
    if not tpl_path.exists():
        # generic fallback
        tpl_path = TEMPLATES / "_generic.html"
    if not tpl_path.exists():
        return None
    tpl = tpl_path.read_text(encoding="utf-8")
    for k, v in lead.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    return tpl


def main() -> int:
    if not LEADS_ACTIVE.exists():
        print("No active leads directory.")
        return 0
    date_dir = DRAFTS_ROOT / datetime.now().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    leads = sorted(LEADS_ACTIVE.glob("*.md"))
    built = 0
    for lp in leads:
        fields = load_lead(lp)
        slug = lp.stem.split("-", 1)[-1]
        primary = fields.get("matched_services", "").split(",")[0].strip() or "unknown"
        body = render_template(primary, fields)
        if not body:
            print(f"  [skip] no template for {primary} — {lp.name}")
            continue
        (date_dir / f"{slug}.html").write_text(body, encoding="utf-8")
        (date_dir / f"{slug}.json").write_text(json.dumps(fields, indent=2), encoding="utf-8")
        built += 1

    print(f"Built {built} drafts -> {date_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
