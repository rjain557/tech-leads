"""
qualify_leads.py -- Stage 2 of the pipeline: semantic lead qualification via Claude.

Stage 1 (scan_jobs.py) is a keyword PREFILTER -- casts a wide net across SerpAPI
google_jobs for anyone hiring a role a Technijian service could cover.
Stage 2 (this script) is the QUALIFIER -- Claude reads each prefiltered lead's
full JD + company context and decides whether the company would realistically
outsource this function to Technijian. Keyword match != fit.

Batching: default 20 leads per API call. 180 leads = 9 API calls instead of 180.
Avoids the tight burst limit on the Claude Code OAuth token (it's shared with the
interactive session, so per-minute request caps kick in fast).

Verdicts route the lead file:
  qualified -> annotate + keep in leads/active/
  rejected  -> move to leads/archived/rejected/{slug}.md
  unclear   -> move to leads/needs-review/{slug}.md

Auth: reads the Claude Code OAuth accessToken from ~/.claude/.credentials.json and
uses it as the x-api-key header -- mirrors _Config.ps1 in the hiring repo.

Runtime:
    python scripts/qualify_leads.py                # all active leads
    python scripts/qualify_leads.py --limit 20     # first N
    python scripts/qualify_leads.py --batch-size 10
    python scripts/qualify_leads.py --dry-run      # no API calls, no file moves
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

# Force UTF-8 stdout so fullwidth parens, en-dashes, CJK company names don't crash cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO = Path(__file__).resolve().parent.parent
CFG = REPO / "config"
ACTIVE = REPO / "leads" / "active"
REJECTED = REPO / "leads" / "archived" / "rejected"
REVIEW = REPO / "leads" / "needs-review"

CLAUDE_CREDS = (
    Path(os.environ["USERPROFILE"]) / ".claude" / ".credentials.json"
    if os.name == "nt" else Path.home() / ".claude" / ".credentials.json"
)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"


# ---- Auth -------------------------------------------------------------------

SECRETS_FILE = REPO / "scripts" / "secrets.json"


def load_api_key() -> str | None:
    """Return anthropicApiKey from secrets.json if present, else None."""
    if not SECRETS_FILE.exists():
        return None
    try:
        data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    k = data.get("anthropicApiKey")
    return k if k and isinstance(k, str) and k.strip() else None


def load_oauth_token() -> str | None:
    """Return Claude Code OAuth accessToken if available, else None."""
    if not CLAUDE_CREDS.exists():
        return None
    try:
        data = json.loads(CLAUDE_CREDS.read_text(encoding="utf-8"))
    except Exception:
        return None
    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        return None
    exp_ms = oauth.get("expiresAt") or 0
    now_ms = int(time.time() * 1000)
    if exp_ms and exp_ms < now_ms:
        print(f"  [warn] OAuth token is past expiresAt ({exp_ms}); API call may 401.")
    return token


def load_auths() -> list[tuple[str, str]]:
    """Return list of (label, token) pairs to try in order. API key first, OAuth fallback."""
    auths: list[tuple[str, str]] = []
    api_key = load_api_key()
    if api_key:
        auths.append(("api_key", api_key))
    oauth = load_oauth_token()
    if oauth:
        auths.append(("oauth", oauth))
    if not auths:
        sys.exit(
            "No Anthropic auth available. Add `anthropicApiKey` to scripts/secrets.json "
            "OR run Claude Code once so ~/.claude/.credentials.json has an OAuth token."
        )
    return auths


# ---- Prompts ----------------------------------------------------------------

QUALIFIER_SYSTEM = """You triage B2B lead candidates for Technijian, an Orange County
managed-services provider. Technijian sells to SMB and mid-market companies that
need to OUTSOURCE a function. It does NOT sell to vendors, competitors, staffing
firms, or enterprises that run their own mature internal org for the function.

You will receive a BATCH of lead candidates. Score each independently. Be decisive:
prefer REJECTED over UNCLEAR when evidence points one way.

Output ONLY a JSON array -- one object per input lead, in the same order. No prose,
no markdown fences, no trailing commentary. Each object MUST have these exact keys:
  "index"        (int, matches the input lead's index)
  "verdict"      ("qualified" | "rejected" | "unclear")
  "confidence"   (float 0.0-1.0)
  "reasoning"    (one sentence grounded in the specific JD/company evidence)
  "likely_buyer" (short title like "CFO", "Practice Administrator", or "")
"""

RULES_BLOCK = """RULES:

REJECTED if ANY of:
- The company IS a vendor/competitor in this space (MSP, IT staffing firm,
  cybersecurity vendor, cloud provider, SaaS vendor selling the same tech,
  compliance consultancy). They hire internal; they don't buy from us.
- The company is Fortune 500 / global enterprise / publicly traded megacorp
  that runs its own in-house IT/security/compliance org at scale
  (e.g. Cisco, Microsoft, UnitedHealth, Hyundai AutoEver, WSP, MaxLinear,
  Adobe, Snowflake, SAIC, Anduril, US Bank, The Hartford, Cognizant).
- Posting is for a strategic/C-level role the company would never outsource
  at their scale (CISO at a regulated giant, Head of AI at a tech unicorn).
- Company is a federal agency / military / state university where procurement
  rules prevent hiring an SoCal MSP.
- Job is at a staffing/consulting firm placing the person elsewhere (Calance,
  VC5 Consulting, Baanyan, VDart, Cypress HCM, Trigyn, Irvine Tech, Elevate,
  Eleven Recruiting, Jobs via Dice, Micro1, etc.).

QUALIFIED if BOTH:
- Company is SMB or mid-market (rough heuristic: <500 employees, under ~$200M
  revenue, not publicly traded, not a household-name enterprise), AND
- The role is hands-on operational work Technijian could absorb as a service
  (solo IT admin, sysadmin, help desk, compliance officer at a clinic,
  M365 admin at a law firm, SOC analyst at an SMB, SDR at a small B2B, etc.)
  OR the company is a regulated SMB (clinic, law firm, small RIA, defense sub
  <200 employees) where ANY compliance/security/IT hire signals real pain.

UNCLEAR only if you genuinely cannot tell company size/type from the JD."""


def build_batch_prompt(leads: list["LeadFile"], services_cfg: dict) -> str:
    """One prompt covering all leads in the batch. Service context is embedded per lead."""
    svc_by_slug = {s["slug"]: s for s in services_cfg.get("services", [])}
    parts = [RULES_BLOCK, "", f"BATCH OF {len(leads)} LEADS:", ""]
    for i, lead in enumerate(leads, 1):
        svc = svc_by_slug.get(lead.primary_service) or {}
        jd = (lead.jd_excerpt or "(no excerpt)")[:1800]  # shorter per-lead so batch fits
        parts.extend([
            f"=== Lead {i} ===",
            f"Service Technijian is offering: {svc.get('name', lead.primary_service)}",
            f"Service pitch: {svc.get('pitch', '')}",
            f"Typical buyers: {', '.join(svc.get('buyer_titles', []))}",
            f"Candidate company: {lead.company or '(unknown)'}",
            f"Role title: {lead.title or '(unknown)'}",
            f"Location: {lead.location or '(unknown)'}",
            f"JD excerpt:",
            jd,
            "",
        ])
    parts.append(
        f"Return a JSON array of EXACTLY {len(leads)} objects, one per lead, in order, "
        f'with keys: index, verdict, confidence, reasoning, likely_buyer.'
    )
    return "\n".join(parts)


# ---- Claude call ------------------------------------------------------------

def _call_claude_once(token: str, prompt: str, max_tokens: int, timeout: int,
                      max_retries: int) -> dict:
    """Single auth attempt with internal backoff on transient errors."""
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": QUALIFIER_SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "x-api-key": token,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    attempt = 0
    while True:
        attempt += 1
        req = Request(ANTHROPIC_URL, data=body, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            status = e.code
            msg = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
            retry_after = 0
            try:
                retry_after = int(e.headers.get("retry-after") or 0)
            except Exception:
                pass
            # 401/403 = auth rejected -> don't retry, surface so we can try next auth.
            if status in (401, 403):
                return {"_error": f"HTTP {status}: {msg[:400]}", "_status": status}
            if status in (429, 500, 502, 503, 504, 529) and attempt <= max_retries:
                base = retry_after if retry_after else min(2 ** (attempt + 2), 60)
                sleep_s = base + random.uniform(0, 2.0)
                print(f"    [retry {attempt}/{max_retries}] HTTP {status}; sleeping {sleep_s:.1f}s")
                time.sleep(sleep_s)
                continue
            return {"_error": f"HTTP {status}: {msg[:400]}", "_status": status}
        except URLError as e:
            if attempt <= max_retries:
                time.sleep(min(2 ** attempt, 30))
                continue
            return {"_error": f"URLError: {e.reason}"}
        except Exception as e:
            return {"_error": f"{type(e).__name__}: {e}"}


def call_claude(auths: list[tuple[str, str]], prompt: str, max_tokens: int = 3500,
                max_retries: int = 5, timeout: int = 120) -> tuple[dict, str]:
    """Try each auth in order. Returns (response, auth_label_used).
    If all auths fail, response contains _error from the last attempt."""
    last: dict = {"_error": "no auths configured"}
    for label, token in auths:
        resp = _call_claude_once(token, prompt, max_tokens, timeout, max_retries)
        if "_error" not in resp:
            return resp, label
        status = resp.get("_status")
        print(f"    [auth:{label}] failed (status={status}); "
              f"{'trying next auth' if label != auths[-1][0] else 'no more auths'}")
        last = resp
    return last, "(none succeeded)"


def parse_batch_verdicts(claude_resp: dict, expected_n: int) -> list[dict] | dict:
    """Return list of verdict dicts, or {"_error": ...}."""
    if "_error" in claude_resp:
        return claude_resp
    try:
        text = claude_resp["content"][0]["text"].strip()
    except Exception:
        return {"_error": f"Unexpected response shape: {json.dumps(claude_resp)[:300]}"}

    # Strip code fences if Claude added them.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.M).strip()

    try:
        arr = json.loads(text)
    except json.JSONDecodeError as e:
        return {"_error": f"JSON parse failed: {e}; body starts: {text[:200]}"}

    if not isinstance(arr, list):
        return {"_error": f"Expected array, got {type(arr).__name__}: {text[:200]}"}
    if len(arr) != expected_n:
        return {"_error": f"Expected {expected_n} verdicts, got {len(arr)}"}

    for v in arr:
        if not isinstance(v, dict) or v.get("verdict") not in ("qualified", "rejected", "unclear"):
            return {"_error": f"Bad verdict entry: {json.dumps(v)[:200]}"}
    return arr


# ---- Lead file I/O ----------------------------------------------------------

@dataclass
class LeadFile:
    path: Path
    fields: dict[str, str]
    body: str

    @property
    def company(self) -> str: return self.fields.get("company", "")
    @property
    def title(self) -> str: return self.fields.get("role_signaling_need", "")
    @property
    def location(self) -> str: return self.fields.get("location", "")

    @property
    def services(self) -> list[str]:
        raw = self.fields.get("matched_services", "")
        return [s.strip() for s in raw.split(",") if s.strip()]

    @property
    def primary_service(self) -> str:
        m = re.search(r"^#\s+.+?—\s+(\S+)\s*$", self.body, re.M)
        if m:
            return m.group(1).strip()
        svcs = self.services
        return svcs[0] if svcs else ""

    @property
    def jd_excerpt(self) -> str:
        m = re.search(r"##\s*JD excerpt\s*\n(.*?)(?:\n##|\Z)", self.body, re.S | re.I)
        if not m:
            return ""
        lines = [re.sub(r"^>\s?", "", ln) for ln in m.group(1).splitlines()]
        return "\n".join(lines).strip()


def parse_lead_file(p: Path) -> LeadFile:
    body = p.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    m = re.search(r"^#\s+(.+?)\s+—\s+", body, re.M)
    if m:
        fields["company"] = m.group(1).strip()
    for line in body.splitlines():
        m = re.match(r"^\-\s+\*\*([^:*]+):\*\*\s+(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "_")
        fields[key] = m.group(2).strip()
    return LeadFile(path=p, fields=fields, body=body)


def annotate_lead(lead: LeadFile, verdict: dict) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    block = "\n".join([
        "",
        "## Qualification",
        "",
        f"- **Verdict:** {verdict.get('verdict')}",
        f"- **Confidence:** {verdict.get('confidence')}",
        f"- **Likely buyer:** {verdict.get('likely_buyer') or '(unknown)'}",
        f"- **Qualified at:** {ts}",
        "",
        f"> {verdict.get('reasoning', '')}",
        "",
    ])
    marker = "\n## Why they fit"
    if marker in lead.body:
        return lead.body.replace(marker, block + marker, 1)
    return lead.body.rstrip() + "\n" + block


def route_lead(lead: LeadFile, verdict: dict, dry_run: bool) -> str:
    new_body = annotate_lead(lead, verdict)
    v = verdict.get("verdict")
    # Binary routing per user direction 2026-04-17: unclear -> rejected. No human triage queue.
    if v == "qualified":
        target = lead.path
    else:
        target = REJECTED / lead.path.name

    if dry_run:
        return f"DRY -> {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_body, encoding="utf-8")
    if target != lead.path:
        try:
            lead.path.unlink()
        except OSError:
            pass
    return f"-> {target.relative_to(REPO)}"


# ---- Orchestrator -----------------------------------------------------------

def chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=20,
                    help="Leads per Claude call (default 20; reduce if context errors)")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="Seconds between batches (default 2; automatic 429 backoff runs on top)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with (CFG / "services.yml").open("r", encoding="utf-8") as f:
        services_cfg = yaml.safe_load(f)

    if args.dry_run:
        auths = [("dry", "DRYRUN")]
    else:
        auths = load_auths()
    print(f"[qualify] auth order: {', '.join(label for label, _ in auths)}")

    files = sorted(ACTIVE.glob("*.md"))
    if args.limit:
        files = files[:args.limit]

    leads = [parse_lead_file(p) for p in files]
    print(f"[qualify] {len(leads)} leads; batch_size={args.batch_size}; "
          f"batches={(len(leads) + args.batch_size - 1) // args.batch_size}; "
          f"model={ANTHROPIC_MODEL}; dry_run={args.dry_run}")

    counts = {"qualified": 0, "rejected": 0, "unclear": 0, "error": 0}

    for b, batch in enumerate(chunk(leads, args.batch_size), 1):
        prompt = build_batch_prompt(batch, services_cfg)
        approx_tokens = len(prompt) // 3  # crude estimate
        print(f"\n[batch {b}] {len(batch)} leads (~{approx_tokens} input tokens)")

        if args.dry_run:
            for i, lead in enumerate(batch, 1):
                print(f"  [{i:02d}] DRY {lead.company[:40]:40s} ({lead.primary_service})")
            continue

        resp, used_auth = call_claude(auths, prompt)
        verdicts = parse_batch_verdicts(resp, expected_n=len(batch))
        if isinstance(verdicts, dict) and "_error" in verdicts:
            print(f"  !! batch error (auth={used_auth}): {verdicts['_error']}")
            counts["error"] += len(batch)
            time.sleep(args.sleep)
            continue
        print(f"  [auth:{used_auth}] batch succeeded")

        for i, (lead, v) in enumerate(zip(batch, verdicts), 1):
            verdict_str = v.get("verdict", "unclear")
            counts[verdict_str] = counts.get(verdict_str, 0) + 1
            routed = route_lead(lead, v, dry_run=False)
            conf = v.get("confidence")
            conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "---"
            safe_co = (lead.company or "")[:40]
            print(f"  [{i:02d}] {verdict_str.upper():9s} {safe_co:40s} "
                  f"({conf_str}) {routed}")

        time.sleep(args.sleep)

    print(f"\n[qualify] done: {counts}")


if __name__ == "__main__":
    main()
