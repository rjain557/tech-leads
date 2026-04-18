"""
enrich_contacts.py -- Stage 2.5: resolve contact email + first name via Hunter.io.

Runs AFTER qualify_leads.py (so we only spend credits on leads that passed)
and BEFORE build_outreach.py (so the draft renderer can use contact_first_name
instead of "team" and Put-DraftsInOutlook.ps1 can populate the To: field).

For each lead in leads/active/*.md:
  1. Parse company + likely_buyer from the header
  2. Hunter /v2/domain-search?company={name} -> resolves domain + returns top
     employees with verified emails, titles, seniority
  3. Score each returned person against the lead's likely_buyer title
  4. Pick the best match; write contact_email + contact_first_name +
     contact_domain back into the lead file as header fields
  5. Cache the company->domain+people result so re-runs don't re-spend credits

Writes:
  leads/active/{slug}.md -- adds `- **Contact email:** ...`,
                            `- **Contact first name:** ...`,
                            `- **Contact title:** ...` header lines
  .cache/hunter_enrichment.json -- cache keyed by lowercase company name

Usage:
  python scripts/enrich_contacts.py
  python scripts/enrich_contacts.py --only mercy
  python scripts/enrich_contacts.py --force  (skip cache)
  python scripts/enrich_contacts.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
LEADS_ACTIVE = REPO / "leads" / "active"
SECRETS = REPO / "scripts" / "secrets.json"
CACHE_DIR = REPO / ".cache"
CACHE_FILE = CACHE_DIR / "hunter_enrichment.json"

HUNTER_BASE = "https://api.hunter.io/v2"


# ---- Config ----------------------------------------------------------------

def load_hunter_key() -> str:
    if not SECRETS.exists():
        sys.exit("scripts/secrets.json missing")
    data = json.loads(SECRETS.read_text(encoding="utf-8"))
    k = data.get("hunterApiKey")
    if not k:
        sys.exit("hunterApiKey not set in scripts/secrets.json")
    return k


def load_cache() -> dict:
    CACHE_DIR.mkdir(exist_ok=True)
    if CACHE_FILE.exists():
        try: return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


# ---- Hunter API ------------------------------------------------------------

def hunter_domain_search(api_key: str, company: str, limit: int = 10) -> dict:
    """Hunter /v2/domain-search?company=... returns domain + employees."""
    url = f"{HUNTER_BASE}/domain-search?" + urlencode({
        "company": company, "limit": limit, "api_key": api_key
    })
    try:
        with urlopen(Request(url), timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8")).get("data", {}) or {}
    except HTTPError as e:
        print(f"    Hunter HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"    Hunter error: {e}", file=sys.stderr)
        return {}


# ---- Title matching --------------------------------------------------------

TITLE_ALIASES = {
    "coo": ["coo", "chief operating officer", "operations director", "head of operations", "vp operations", "vp of operations"],
    "ceo": ["ceo", "chief executive officer", "founder", "president", "managing partner"],
    "cfo": ["cfo", "chief financial officer", "finance director", "vp finance", "vp of finance"],
    "cio": ["cio", "chief information officer", "it director", "vp of it", "head of it"],
    "cto": ["cto", "chief technology officer", "vp engineering", "vp of engineering", "head of engineering"],
    "ciso": ["ciso", "chief information security officer", "security director", "vp security"],
    "cco": ["cco", "chief compliance officer", "compliance officer", "privacy officer", "compliance director", "compliance manager"],
    "cro": ["cro", "chief revenue officer", "vp sales", "vp of sales", "head of sales", "sales director"],
    "cmo": ["cmo", "chief marketing officer", "vp marketing", "head of marketing", "marketing director"],
    "hr":  ["chro", "chief hr officer", "hr director", "vp hr", "head of hr", "head of people"],
}

def title_variants(raw_title: str) -> list[str]:
    t = (raw_title or "").strip().lower()
    variants = {t}
    # Direct alias match
    for key, aliases in TITLE_ALIASES.items():
        if any(a in t for a in aliases):
            variants.update(aliases)
    # Department hints
    if "compliance" in t or "privacy" in t: variants.update(TITLE_ALIASES["cco"])
    if "operations" in t: variants.update(TITLE_ALIASES["coo"])
    if "sales" in t or "revenue" in t: variants.update(TITLE_ALIASES["cro"])
    if "marketing" in t: variants.update(TITLE_ALIASES["cmo"])
    if "it " in t or t.startswith("it ") or "information" in t: variants.update(TITLE_ALIASES["cio"])
    if "technology" in t or "engineering" in t: variants.update(TITLE_ALIASES["cto"])
    if "finance" in t or "financial" in t or t == "cfo": variants.update(TITLE_ALIASES["cfo"])
    return list(variants)


def score_person(p: dict, target_title: str) -> int:
    pos = (p.get("position") or "").lower()
    if not pos: return 0
    target = target_title.lower()
    variants = title_variants(target_title)
    # Exact or substring match
    if target in pos or pos in target: return 100
    # Alias hit
    for v in variants:
        if v and v in pos: return 80
    # Seniority fallback
    sen = (p.get("seniority") or "").lower()
    return {"executive": 55, "c_suite": 60, "director": 45, "manager": 30, "senior": 20}.get(sen, 10)


# ---- Lead file parsing + writeback ----------------------------------------

HEADER_RE = re.compile(r"^-\s+\*\*([^:*]+):\*\*\s+(.*)$", re.MULTILINE)
H1_RE = re.compile(r"^#\s+([^\n]+?)\s*$", re.MULTILINE)


def parse_lead(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fields = {}
    for m in HEADER_RE.finditer(text):
        fields[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
    h1 = H1_RE.search(text)
    if h1:
        company = re.sub(r"\s+[\u2014\u2013\-]{1,2}\s+\S+$", "", h1.group(1).strip()).strip()
        fields["company"] = company
    return {"path": path, "text": text, "fields": fields}


def update_lead_file(lead: dict, enrichment: dict) -> None:
    """Insert/replace contact_* header lines after the last existing header."""
    text = lead["text"]
    lines_to_add = []
    if enrichment.get("email"):       lines_to_add.append(f"- **Contact email:** {enrichment['email']}")
    if enrichment.get("first_name"):  lines_to_add.append(f"- **Contact first name:** {enrichment['first_name']}")
    if enrichment.get("last_name"):   lines_to_add.append(f"- **Contact last name:** {enrichment['last_name']}")
    if enrichment.get("title"):       lines_to_add.append(f"- **Contact title:** {enrichment['title']}")
    if enrichment.get("domain"):      lines_to_add.append(f"- **Company domain:** {enrichment['domain']}")
    if not lines_to_add: return

    # Remove any prior contact_* lines so re-runs are idempotent
    text = re.sub(r"^-\s+\*\*(Contact email|Contact first name|Contact last name|Contact title|Company domain):\*\*.*\n", "", text, flags=re.MULTILINE)

    # Find the last header line (before the first ## section)
    first_section = re.search(r"^##\s+", text, re.MULTILINE)
    if first_section:
        insert_at = first_section.start()
        # backtrack past any blank lines
        prefix = text[:insert_at].rstrip() + "\n"
        suffix = text[insert_at:]
        new_text = prefix + "\n".join(lines_to_add) + "\n\n" + suffix
    else:
        new_text = text.rstrip() + "\n" + "\n".join(lines_to_add) + "\n"

    lead["path"].write_text(new_text, encoding="utf-8")


# ---- Main ------------------------------------------------------------------

def enrich_one(api_key: str, cache: dict, lead: dict, force: bool, dry: bool) -> dict:
    company = lead["fields"].get("company", "").strip()
    buyer   = lead["fields"].get("likely_buyer", "").strip()
    if not company:
        return {"status": "skip", "reason": "no company"}

    cache_key = company.lower()
    if not force and cache_key in cache:
        resp = cache[cache_key]
    else:
        if dry:
            return {"status": "skip", "reason": "dry-run, not cached"}
        print(f"    -> Hunter domain-search: {company}")
        resp = hunter_domain_search(api_key, company) or {}
        cache[cache_key] = resp
        save_cache(cache)
        time.sleep(0.3)

    domain = resp.get("domain") or ""
    emails = resp.get("emails") or []
    if not domain or not emails:
        return {"status": "no_match", "domain": domain or None}

    # Score each candidate against the likely_buyer title
    ranked = sorted(
        [(score_person(p, buyer), p) for p in emails if p.get("value")],
        key=lambda x: (-x[0], -int(x[1].get("confidence") or 0)),
    )
    if not ranked or ranked[0][0] < 10:
        return {"status": "no_match", "domain": domain}

    pick_score, pick = ranked[0]
    return {
        "status": "ok",
        "score": pick_score,
        "email": pick.get("value"),
        "first_name": pick.get("first_name"),
        "last_name": pick.get("last_name"),
        "title": pick.get("position"),
        "seniority": pick.get("seniority"),
        "confidence": pick.get("confidence"),
        "verified": (pick.get("verification") or {}).get("status") == "valid",
        "domain": domain,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default=None, help="Slug substring filter")
    ap.add_argument("--force", action="store_true", help="Bypass cache")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = load_hunter_key()
    cache = load_cache()

    files = sorted(LEADS_ACTIVE.glob("*.md"))
    if args.only:
        files = [f for f in files if args.only.lower() in f.stem.lower()]
    if not files:
        print("no leads found"); return 0

    print(f"Enriching {len(files)} leads (cache={len(cache)}) via Hunter.io\n")
    ok = no_match = skip = 0
    for f in files:
        lead = parse_lead(f)
        slug = f.stem.split("-", 1)[-1]
        result = enrich_one(api_key, cache, lead, args.force, args.dry_run)
        if result["status"] == "ok":
            ok += 1
            v = "valid" if result["verified"] else "unverified"
            print(f"  [ok]   {slug:<26} -> {result['first_name']} {result['last_name']} ({result['title']}) {result['email']} score={result['score']} conf={result['confidence']} {v}")
            if not args.dry_run:
                update_lead_file(lead, result)
        elif result["status"] == "no_match":
            no_match += 1
            print(f"  [miss] {slug:<26} -> domain={result.get('domain','?')}")
        else:
            skip += 1
            print(f"  [skip] {slug:<26} -> {result.get('reason','?')}")

    print(f"\nDone. ok={ok} no_match={no_match} skip={skip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
