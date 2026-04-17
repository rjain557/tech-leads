"""
scan_jobs.py — Lead scanner for tech-leads pipeline, powered by SerpAPI Google Jobs.

SerpAPI's `google_jobs` engine aggregates Indeed / LinkedIn / Glassdoor / ZipRecruiter /
Monster into one clean JSON response. One API call per (service × scope) — so we
trade six fragile scraper selectors for one API.

Runtime:
    python scripts/scan_jobs.py --scope local
    python scripts/scan_jobs.py --scope remote
    python scripts/scan_jobs.py --scope all --dry-run       # print queries, no API calls
    python scripts/scan_jobs.py --scope all --max-queries 4 # cap for testing
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import yaml  # PyYAML
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")


REPO = Path(__file__).resolve().parent.parent
CFG = REPO / "config"
TRACKING = REPO / "tracking"
LEADS_ACTIVE = REPO / "leads" / "active"
SECRETS_FILE = REPO / "scripts" / "secrets.json"

SERPAPI_BASE = "https://serpapi.com/search.json"
# Cap top-N signal titles to combine in a single OR query per service — keeps per-run
# SerpAPI credit usage small (~22 calls/run) while still covering the core titles.
TOP_N_TITLES_PER_SERVICE = 6


# ── Config loading ─────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_config() -> tuple[dict, dict, dict]:
    services = load_yaml(CFG / "services.yml")
    portals = load_yaml(CFG / "portals.yml")
    targeting = load_yaml(CFG / "targeting.yml")
    return services, portals, targeting


def load_secrets() -> dict[str, Any]:
    if not SECRETS_FILE.exists():
        sys.exit(f"Missing {SECRETS_FILE}. See CLAUDE.md.")
    with SECRETS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


# ── Models ─────────────────────────────────────────────────────────────────────

@dataclass
class Posting:
    service_slug: str
    query: str
    scope: str
    title: str
    company: str
    location: str
    posted_date: str | None
    url: str
    description_snippet: str = ""
    job_id: str = ""
    via: str = ""
    extensions: list[str] = field(default_factory=list)


@dataclass
class Lead:
    company: str
    company_slug: str
    services: list[str]
    primary_service: str
    score: float
    scope: str
    best_posting: Posting
    all_postings: list[Posting] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    priority: str = "warm"


# ── Query building ─────────────────────────────────────────────────────────────

def build_queries(services: dict, scope: str) -> list[tuple[str, str]]:
    """
    One query per service — top-N signal titles joined with OR. Returns [(slug, query)].
    """
    out: list[tuple[str, str]] = []
    for svc in services.get("services", []):
        slug = svc["slug"]
        titles = svc.get("signal_job_titles", [])[:TOP_N_TITLES_PER_SERVICE]
        if not titles:
            continue
        # Google Jobs accepts "title1" OR "title2" OR ... in its q field.
        q_parts = [f'"{t}"' for t in titles]
        query = " OR ".join(q_parts)
        out.append((slug, query))
    return out


# ── SerpAPI fetch ──────────────────────────────────────────────────────────────

def fetch_serpapi_google_jobs(
    query: str,
    scope: str,
    api_key: str,
    portals_cfg: dict,
    timeout: int = 45,
) -> tuple[list[dict], dict]:
    """
    Call SerpAPI google_jobs engine once and return (jobs_results, search_metadata).
    Scope maps to:
      local  -> location=Irvine,California; no remote chip
      remote -> no location; chips=requirements:remote
    Freshness: chips=date_posted:week (last 7 days).
    """
    params = {
        "engine": "google_jobs",
        "q": query,
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
    }
    scopes = portals_cfg.get("scopes", {})
    if scope == "local":
        loc = scopes.get("local", {}).get("location", "Irvine, California")
        params["location"] = loc
    elif scope == "remote":
        # Google Jobs remote filter: ltype=1 plus a broad US location
        params["location"] = "United States"
        params["ltype"] = "1"

    # Date-posted chip: "week" = last 7 days
    params["chips"] = "date_posted:week"

    url = f"{SERPAPI_BASE}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "tech-leads-scanner/0.1"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return [], {"error": f"HTTP {e.code}: {body[:200]}"}
    except URLError as e:
        return [], {"error": f"URL error: {e.reason}"}
    except Exception as e:
        return [], {"error": f"{type(e).__name__}: {e}"}

    if data.get("error"):
        return [], {"error": data["error"]}

    return data.get("jobs_results") or [], data.get("search_metadata") or {}


def parse_serp_posting(raw: dict, service_slug: str, query: str, scope: str) -> Posting:
    apply_opts = raw.get("apply_options") or []
    url = apply_opts[0].get("link") if apply_opts else raw.get("share_link", "")
    ext = raw.get("detected_extensions") or {}
    posted = ext.get("posted_at")  # e.g., "2 days ago"; may be missing
    desc = (raw.get("description") or "").strip()
    return Posting(
        service_slug=service_slug,
        query=query,
        scope=scope,
        title=raw.get("title", ""),
        company=raw.get("company_name", ""),
        location=raw.get("location", ""),
        posted_date=posted,
        url=url or "",
        description_snippet=desc[:2000],
        job_id=raw.get("job_id", ""),
        via=raw.get("via", ""),
        extensions=raw.get("extensions") or [],
    )


# ── Scoring ────────────────────────────────────────────────────────────────────

TITLE_MATCH_RE_CACHE: dict[str, re.Pattern] = {}


def match_title(posting_title: str, signal_titles: Iterable[str]) -> bool:
    t = posting_title.lower()
    for s in signal_titles:
        k = s.lower()
        if k not in TITLE_MATCH_RE_CACHE:
            TITLE_MATCH_RE_CACHE[k] = re.compile(r"\b" + re.escape(k) + r"\b", re.I)
        if TITLE_MATCH_RE_CACHE[k].search(t):
            return True
    return False


def count_keyword_matches(hay: str, keywords: Iterable[str]) -> tuple[int, list[str]]:
    hl = hay.lower()
    hits = [kw for kw in keywords if kw.lower() in hl]
    return len(hits), hits


def score_posting(posting: Posting, services: dict, targeting: dict) -> tuple[float, list[str], list[str]]:
    w = targeting["scoring"]
    reasons: list[str] = []
    matched: list[str] = []
    score = w["base"]
    hay = " ".join([posting.title, posting.description_snippet])

    for svc in services["services"]:
        title_hit = match_title(posting.title, svc.get("signal_job_titles", []))
        kw_count, kw_hits = count_keyword_matches(hay, svc.get("signal_keywords", []))
        if not (title_hit or kw_count > 0):
            continue
        matched.append(svc["slug"])
        if title_hit:
            score += w["title_match_weight"]
            reasons.append(f"{svc['slug']} title match: '{posting.title}'")
        if kw_count:
            score += min(kw_count * w["keyword_match_weight"], w["keyword_match_cap"])
            reasons.append(f"{svc['slug']} kw hits: {', '.join(kw_hits[:4])}")
        for strong in svc.get("strong_signals", []):
            if any(tok in hay.lower() for tok in _loose_tokens(strong)):
                score += w["strong_signal_bonus"]
                reasons.append(f"{svc['slug']} strong signal: {strong}")
                break

    if posting.scope == "local":
        score += w["local_scope_bonus"]
        reasons.append("local scope bonus")

    if len(matched) > 1:
        score += w["multi_service_bonus"]
        reasons.append(f"multi-service fit ({len(matched)})")

    age = _posting_age_days(posting.posted_date)
    if age is not None:
        for rule in w.get("recency_bonus", []):
            if age <= rule["max_age_days"]:
                score += rule["bonus"]
                reasons.append(f"recency bonus (≤{rule['max_age_days']}d)")
                break

    return score, matched, reasons


def _loose_tokens(pat: str) -> list[str]:
    toks = re.findall(r"[a-z0-9/+\-]{4,}", pat.lower())
    stop = {"hire", "hires", "hiring", "with", "that", "this", "mentions", "jobs", "role", "company"}
    return [t for t in toks if t not in stop][:4]


def _posting_age_days(posted: str | None) -> int | None:
    if not posted:
        return None
    m = re.match(r"^(\d+)\s*(day|days|hour|hours|hr|hrs)\s*ago", posted.strip(), re.I)
    if m:
        n = int(m.group(1))
        return 0 if m.group(2).lower().startswith(("hour", "hr")) else n
    try:
        dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


# ── Dedup + persistence ────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:80] or "company"


def load_known() -> dict[str, Any]:
    with (TRACKING / "known-companies.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def save_known(data: dict[str, Any]) -> None:
    data["last_scan_utc"] = datetime.now(timezone.utc).isoformat()
    with (TRACKING / "known-companies.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def already_seen_recently(known: dict, company_slug: str, role_bucket: str, dedup_days: int) -> bool:
    rec = known.get("companies", {}).get(company_slug, {}).get(role_bucket)
    if not rec:
        return False
    try:
        last = datetime.fromisoformat(rec["last_seen_utc"])
    except Exception:
        return False
    return (datetime.now(timezone.utc) - last).days < dedup_days


def write_lead_file(lead: Lead, next_seq: int) -> Path:
    LEADS_ACTIVE.mkdir(parents=True, exist_ok=True)
    p = LEADS_ACTIVE / f"{next_seq:03d}-{lead.company_slug}.md"
    bp = lead.best_posting
    body = [
        f"# {lead.company} — {lead.primary_service}",
        "",
        f"- **Score:** {lead.score:.2f}",
        f"- **Priority:** {lead.priority}",
        f"- **Scope:** {lead.scope}",
        f"- **Matched services:** {', '.join(lead.services)}",
        f"- **Role signaling need:** {bp.title}",
        f"- **Posted:** {bp.posted_date or 'unknown'}",
        f"- **Posting URL:** {bp.url}",
        f"- **Location:** {bp.location}",
        f"- **Via:** {bp.via}",
        "",
        "## Why they fit",
        *[f"- {r}" for r in lead.reasons],
        "",
        "## JD excerpt",
        f"> {bp.description_snippet[:1200]}",
        "",
        "## Status",
        "- [ ] Reviewed by rjain",
        "- [ ] Sent",
        "- [ ] Reply received",
        "- [ ] Meeting booked",
        "- [ ] Closed won / lost",
        "",
    ]
    p.write_text("\n".join(body), encoding="utf-8")
    return p


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_scan(scope: str, dry_run: bool = False, max_queries: int | None = None) -> dict:
    services, portals, targeting = load_all_config()
    secrets = load_secrets()
    api_key = secrets.get("serpApiKey")
    if not api_key and not dry_run:
        sys.exit("secrets.json missing serpApiKey — see docs/setup.md")

    queries = build_queries(services, scope)
    if max_queries:
        queries = queries[:max_queries]
    print(f"[scan] scope={scope} queries={len(queries)} dry_run={dry_run}")

    jitter = portals["scan_strategy"]["delay_between_requests_ms"]
    all_postings: list[Posting] = []

    for (slug, q) in queries:
        if dry_run:
            print(f"  [dry] {slug:24s} q={q[:90]}")
            continue
        print(f"  [api] {slug:24s} q={q[:90]}")
        raw_jobs, meta = fetch_serpapi_google_jobs(q, scope, api_key, portals)
        if meta.get("error"):
            print(f"    !! {meta['error']}")
            continue
        print(f"    got {len(raw_jobs)} postings")
        for raw in raw_jobs:
            all_postings.append(parse_serp_posting(raw, slug, q, scope))
        time.sleep(random.uniform(jitter[0], jitter[1]) / 1000.0)

    if dry_run:
        return {"postings": 0, "hot": 0, "warm": 0}

    known = load_known()
    next_seq = 1
    if LEADS_ACTIVE.exists():
        existing = sorted(LEADS_ACTIVE.glob("*-*.md"))
        if existing:
            m = re.match(r"^(\d+)-", existing[-1].name)
            if m:
                next_seq = int(m.group(1)) + 1

    # Aggregator reposts — shallow JDs, always rejected by qualifier, waste credits.
    # Filter out at the prefilter stage so qualifier only sees real employers.
    AGGREGATORS = {
        "virtual vocations", "flexjobs", "jobgether", "jobs via dice", "whatjobs",
        "jobleads", "bebee", "ziprecruiter", "jobsora", "joveo", "jooble", "neuvoo",
        "learn4good", "careerbuilder", "adzuna", "jobomas", "recruit.net",
    }

    hot, warm, skipped, aggregator_skipped = 0, 0, 0, 0
    dedup_days = targeting["outreach"]["dedup_days"]
    for posting in all_postings:
        if not posting.company or not posting.title:
            continue
        if posting.company.strip().lower() in AGGREGATORS:
            aggregator_skipped += 1
            continue
        cslug = slugify(posting.company)
        score, matched, reasons = score_posting(posting, services, targeting)
        if score < targeting["scoring"]["priority_threshold_warm"]:
            continue
        bucket = matched[0] if matched else "unknown"
        if already_seen_recently(known, cslug, bucket, dedup_days):
            skipped += 1
            continue
        priority = "hot" if score >= targeting["scoring"]["priority_threshold_hot"] else "warm"
        lead = Lead(
            company=posting.company, company_slug=cslug, services=matched,
            primary_service=bucket, score=score, scope=posting.scope,
            best_posting=posting, all_postings=[posting],
            reasons=reasons, priority=priority,
        )
        if priority == "hot":
            write_lead_file(lead, next_seq)
            next_seq += 1
            hot += 1
        else:
            warm += 1
        known.setdefault("companies", {}).setdefault(cslug, {})[bucket] = {
            "last_seen_utc": datetime.now(timezone.utc).isoformat(),
            "last_score": score,
            "last_title": posting.title,
            "last_url": posting.url,
            "last_scope": posting.scope,
        }

    save_known(known)
    print(f"[scan] done: postings={len(all_postings)} hot={hot} warm={warm} dedup_skipped={skipped} aggregator_skipped={aggregator_skipped}")
    return {"postings": len(all_postings), "hot": hot, "warm": warm, "skipped": skipped, "aggregator_skipped": aggregator_skipped}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["local", "remote", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-queries", type=int, default=None, help="Cap queries for testing")
    args = ap.parse_args()
    scopes = ["local", "remote"] if args.scope == "all" else [args.scope]
    for s in scopes:
        run_scan(s, dry_run=args.dry_run, max_queries=args.max_queries)


if __name__ == "__main__":
    main()
