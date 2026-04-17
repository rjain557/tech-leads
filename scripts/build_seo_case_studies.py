"""Build SEO/AI/dev case studies from the technijian-seo/sdlc repo.

Reads c:/VSCode/technijian-seo-sdlc/ (a shallow clone). Processes:

  1. sdlc/clients/{CODE}/{domain}/09_Work_Done/2026_Work_Log.md
        -> per-client SEO case study (anonymized by industry)
  2. sdlc/.antigravity/skills/*.md
        -> Antigravity agent skills inventory (AI capability)
  3. sdlc/.agents/workflows/*.md
        -> AI workflow definitions (HeyGen video, etc.)
  4. sdlc/n8n_workflows/templates/*.json
        -> n8n automation templates (names only; bodies may contain creds)
  5. root + sdlc scripts (generate_all_status_reviews, weekly_pipeline,
     heygen_monitor, seo_team_skills_analyzer)
        -> dev-capability descriptors

All client + employee + domain identifiers are scrubbed before writing.
Outputs go to tracking/kb/case-studies/{industry}/seo-*.md and
tracking/kb/case-studies/_capabilities/{ai-dev-*.md} (committed, anonymized).
"""
from __future__ import annotations
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEO_REPO = Path("c:/VSCode/technijian-seo-sdlc")
CS_DIR = REPO / "tracking" / "kb" / "case-studies"
CAP_DIR = CS_DIR / "_capabilities"
CAP_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO / "scripts"))
from build_case_studies import derive_aliases, scrub  # reuse core scrubber


# ---------- SEO client mapping ----------

# CODE -> (domain, full_name, industry, industry-pseudonym noun)
SEO_CLIENTS = {
    "FOR":   ("falconerofredlands.com", "Falconer of Redlands",
              "Hospitality", "restaurant"),
    "TOR":   ("tartanofredlands.com", "Tartan of Redlands",
              "Hospitality", "restaurant"),
    "CSS":   ("customsiliconsolutions.com", "Custom Silicon Solutions",
              "Manufacturing", "semiconductor-design firm"),
    "EBRMD": ("drface.com", "Ernest B Robinson MD",
              "Healthcare", "plastic-surgery practice"),
    "PCAP":  (None, "Pet Care Plus",
              "Healthcare", "veterinary practice"),
    "VWC":   ("visionwisecapital.com", "VisionWise Capital",
              "Financial Services", "private-equity advisory firm"),
}

# Scrubbed global: all SEO team member names and emails
SEO_TEAM = [
    ("Puneet Kumar",   "pkumar@technijian.com"),
    ("Saroj Kumari",   "skumari@technijian.com"),
    ("Mohit Pandey",   "mpandey@technijian.com"),
    ("Vaishali Rathor","vrathor@technijian.com"),
]

EMPLOYEE_PLACEHOLDER = "an assigned SEO specialist"


# ---------- Utilities ----------

TAG = re.compile(r"<[^>]+>")
CSS_RESIDUE = re.compile(
    r"\*\]:[^\s\"']+|data-[a-z-]+=\"[^\"]*\"?|data-[a-z-]+=\"[^\"]*$|"
    r"tabindex=\"-?\d+\"|tabindex=-?\d+|"
    r"scroll-mt-\[[^\]]*\]|scroll-mt-\([^)]*\)|calc\([^)]*\)|"
    r"pointer-events-[a-z-]+|min\([^)]*\)|max\([^)]*\)|"
    r"-?-?(?:header|shadow)-[a-z-]+|text-token-[a-z-]+|dir=\"auto\"|"
    r"supports-\[[^\]]*\]:\[[^\]]*\]|content-visibility:[a-z]+|"
    r"focus:[a-z:-]+|has-data-[a-z-]+:[a-z-]*|"
    r"\[[\w:()+,./*-]+\](?::[a-z-]+)?|"
    r"\"\s*tabindex|\"\s*dir=",
    re.I,
)


def clean_text(s: str) -> str:
    s = html.unescape(s or "")
    s = TAG.sub(" ", s)
    s = CSS_RESIDUE.sub(" ", s)
    s = s.replace("\u00A0", " ").replace("\u200B", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def scrub_with(aliases: list[str], industry: str, team_names: list[str],
               domains: list[str], text: str) -> str:
    """Apply multi-layer scrub: client aliases + team names + domains."""
    out = clean_text(text)
    # Domain scrub first (before alias, because domains often contain the alias)
    for d in domains:
        if not d:
            continue
        out = re.sub(re.escape(d), "the client website", out, flags=re.I)
        # Also scrub naked-domain variants (without TLD) e.g. "falconerofredlands"
        stem = d.split(".")[0]
        if len(stem) >= 6:
            out = re.sub(rf"\b{re.escape(stem)}\b", "the client website", out, flags=re.I)
    # Team names
    for name in team_names:
        out = re.sub(rf"\b{re.escape(name)}\b", EMPLOYEE_PLACEHOLDER, out, flags=re.I)
        # First-name-only form
        first = name.split()[0]
        if len(first) >= 4:
            out = re.sub(rf"\b{re.escape(first)}\b", EMPLOYEE_PLACEHOLDER, out, flags=re.I)
    # Core alias scrub (client names)
    out = scrub(out, aliases, industry)
    # Collapse multiples
    out = re.sub(r"(?:the client website[ ,.]*){2,}", "the client website ", out)
    out = re.sub(rf"(?:{re.escape(EMPLOYEE_PLACEHOLDER)}[ ,.]*){{2,}}",
                 EMPLOYEE_PLACEHOLDER + " ", out)
    # Monthly-summary rows have "an assigned SEO specialist: N/Xh; an assigned SEO specialist: N/Yh; ..."
    # Compress into a single "specialists: sum/total-hr" token.
    def _compress_employee_tallies(m):
        block = m.group(0)
        entries = re.findall(r"an assigned SEO specialist:\s*(\d+)\s*/\s*([\d.]+)h", block)
        if not entries:
            return block
        n = sum(int(e) for e, _ in entries)
        h = sum(float(H) for _, H in entries)
        return f"specialists: {n}/{h:.1f}h"
    out = re.sub(r"(?:an assigned SEO specialist:\s*\d+\s*/\s*[\d.]+h\s*;?\s*){2,}",
                 _compress_employee_tallies, out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def read_if_exists(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


# ---------- per-client SEO case studies ----------

def _build_global_pools():
    """Cross-client name + domain pool so references in one client's log to
    a different client's name or domain get scrubbed."""
    all_aliases: list[str] = []
    all_domains: list[str] = []
    for c, (dom, name, _ind, _pseud) in SEO_CLIENTS.items():
        for a in derive_aliases(name, c):
            if len(a) >= 4:
                all_aliases.append(a)
        if dom:
            all_domains.append(dom)
            all_domains.append("www." + dom)
    # Dedup longest-first
    all_aliases = sorted(set(all_aliases), key=len, reverse=True)
    all_domains = sorted(set(all_domains), key=len, reverse=True)
    return all_aliases, all_domains


GLOBAL_SEO_ALIASES, GLOBAL_SEO_DOMAINS = _build_global_pools()


def build_client_case_study(code: str) -> dict | None:
    domain, full_name, industry, pseudonym = SEO_CLIENTS[code]
    # Find the 09_Work_Done log
    candidates = list(SEO_REPO.rglob(f"sdlc/clients/{code}/**/09_Work_Done/2026_Work_Log.md"))
    if not candidates:
        return None
    log = read_if_exists(candidates[0])
    # Pull totals + monthly summary section + narrative highlights
    totals = ""
    monthly = ""
    tm = re.search(r"## Totals\s+\n(.+?)(?=\n## )", log, re.S)
    if tm:
        totals = tm.group(1).strip()
    mm = re.search(r"## Monthly Summary\s+\n(.+?)(?=\n## )", log, re.S)
    if mm:
        monthly = mm.group(1).strip()

    # Aliases: own client (longest first) + every other SEO client
    own_aliases = derive_aliases(full_name, code)
    aliases = list(dict.fromkeys(own_aliases + GLOBAL_SEO_ALIASES))
    team_names = [n for n, _ in SEO_TEAM]

    # Domain forms: own + every other SEO client's domain + any other .com referenced in the log
    domain_list = []
    if domain:
        domain_list.append(domain)
        domain_list.append("www." + domain)
    domain_list.extend(GLOBAL_SEO_DOMAINS)
    for m in re.finditer(r"\b([a-z0-9-]+\.com)\b", log, re.I):
        domain_list.append(m.group(1))
    # Longest first so "www.foo.com" replaces before "foo.com"
    domain_list = sorted(dict.fromkeys(domain_list), key=len, reverse=True)

    def do_scrub(s: str) -> str:
        return scrub_with(aliases, industry, team_names, domain_list, s)

    # Compose the case study
    title = f"SEO Engagement — {pseudonym.capitalize()}"
    out = [f"# {title}", ""]
    out.append(f"- **Industry:** {industry}")
    out.append(f"- **Engagement type:** ongoing monthly SEO + content + WordPress")
    out.append(f"- **Source:** 2026 work log from the Technijian SEO SDLC repo")
    if totals:
        out.append(f"- **Scope:** {do_scrub(totals)}")
    out.append("")

    if monthly:
        out.append("## Monthly activity")
        out.append("")
        out.append(do_scrub(monthly))
        out.append("")

    # Pull narrative highlights: individual note excerpts from the monthly sections
    out.append("## Representative work (anonymized)")
    out.append("")
    # Match "| Note (excerpt) |" table rows and extract the notes
    note_rows = re.findall(r"\|\s*\d{4}-\d{2}-\d{2}\s*\|[^|]+\|\s*\d+\s*\|\s*[\d.]+\s*\|\s*([^|]+)\|\s*([^|]+)\|",
                           log)
    # note_rows elements: (Title, Note(excerpt))
    seen = set()
    bullet_count = 0
    for t, n in note_rows:
        note = do_scrub(n.strip())
        # Skip if note is too short or is mostly CSS fragment residue
        meaningful = re.sub(r"[^a-zA-Z ]", " ", note)
        meaningful = re.sub(r"\s+", " ", meaningful).strip()
        if len(meaningful) < 40:
            continue
        # Dedup by first 120 chars lowercased with whitespace collapsed
        key = re.sub(r"\s+", " ", note[:140].lower())
        # Also dedup by first 60 chars only (catches "All updates for the client website..." variants)
        short_key = key[:60]
        if key in seen or short_key in seen:
            continue
        seen.add(key); seen.add(short_key)
        title_scrubbed = do_scrub(t.strip())
        out.append(f"- **{title_scrubbed}** — {note[:320]}")
        bullet_count += 1
        if bullet_count >= 10:
            break
    if bullet_count == 0:
        out.append("_(No notes passed the length threshold — see totals.)_")
    out.append("")

    out.append("## Outreach-ready summary")
    out.append("")
    summary = (
        f"Ongoing SEO, content, and WordPress maintenance for a {pseudonym} — "
        f"technical fixes against SEMrush / HOTH audits, monthly keyword research and "
        f"ranking tracking, weekly reporting, and continuous on-page improvements. "
        f"Delivered through a 4-person specialist team with a standing weekly review cadence."
    )
    out.append(summary)
    out.append("")

    ind_dir = CS_DIR / industry.lower().replace(" ", "-").replace("/", "-")
    ind_dir.mkdir(parents=True, exist_ok=True)
    base = f"seo-{pseudonym.replace(' ', '-')}"
    fpath = ind_dir / f"{base}.md"
    # Collision handling: FOR + TOR both slug to `seo-restaurant.md`. Number them.
    n = 2
    while fpath.exists():
        fpath = ind_dir / f"{base}-{n:02d}.md"
        n += 1
    fpath.write_text("\n".join(out), encoding="utf-8")
    return {"code": code, "industry": industry, "file": str(fpath.relative_to(CS_DIR))}


# ---------- AI / Dev capability case studies (industry-agnostic) ----------

def build_capability_ai_agents() -> dict:
    """Case study on the Google Antigravity agent + skill architecture."""
    skills_dir = SEO_REPO / "sdlc" / ".antigravity" / "skills"
    skills = sorted(p.stem for p in skills_dir.glob("skill-*.md")) if skills_dir.exists() else []
    # Human-readable versions
    def pretty(s):
        # drop 'skill-' prefix
        s = s[len("skill-"):] if s.lower().startswith("skill-") else s
        return s.replace("-", " ").title()
    lines = [
        "# AI Agent Architecture for SEO Delivery",
        "",
        "- **Capability:** AI + Automation",
        "- **Applies to:** Any industry running a content-heavy SEO program",
        "",
        "## What was built",
        "",
        "A multi-agent SEO delivery system built on Google Antigravity. "
        "Each specialist capability is encoded as a discrete agent Skill, "
        "allowing a small human team (4 FTE) to operate as if it were a "
        "10-15 person agency.",
        "",
        f"**{len(skills)} specialized skills** live in the agent runtime, including:",
        "",
    ]
    for s in skills:
        lines.append(f"- {pretty(s)}")
    lines += [
        "",
        "## How it works in practice",
        "",
        "- **MCP servers** wire the agents to live tools: SEMrush (audit + rank tracking), "
        "  Microsoft Graph (Planner/Teams), Playwright (site verification), n8n (workflow "
        "  automation), HeyGen (avatar-driven video).",
        "- **Skill composition:** the Planner skill decomposes a weekly status review into "
        "  tasks, routes each to the right specialist Skill (content refinery, local prime, "
        "  WordPress architect, paid-media manager, etc.), and assembles the result.",
        "- **Brand consistency:** a single `technijian-voice` skill enforces tone across every "
        "  client-facing artifact the agents generate.",
        "",
        "## Outcomes",
        "",
        "- Weekly PPTX status reviews generated automatically per client, "
        "  with speaker notes and structured metrics JSON. ~8 clients produced in minutes "
        "  instead of days.",
        "- Content pipeline, paid-media reporting, and client onboarding each templatized "
        "  as an n8n workflow — new clients onboard in hours.",
        "- HeyGen workflow produces branded explainer videos from a script + avatar ID, "
        "  with automated polling and delivery to the client drive.",
        "",
        "## Outreach-ready summary",
        "",
        "We operate a multi-agent AI system that automates the busywork of SEO delivery — "
        "status reviews, content routing, site verification, ranking analysis, even "
        "branded video — so the human specialists focus on strategy and client "
        "relationships. It's production, not experimental.",
        "",
    ]
    fpath = CAP_DIR / "ai-agent-architecture.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return {"capability": "AI Agents", "file": str(fpath.relative_to(CS_DIR))}


def build_capability_n8n() -> dict:
    tmpl_dir = SEO_REPO / "sdlc" / "n8n_workflows" / "templates"
    tmpls = sorted(p.name for p in tmpl_dir.glob("*.json")) if tmpl_dir.exists() else []
    def pretty(n): return re.sub(r"^\d+_", "", n.rsplit(".",1)[0]).replace("_", " ")
    lines = [
        "# n8n Workflow Automation",
        "",
        "- **Capability:** Dev + Automation",
        "- **Applies to:** Any services business with repeatable delivery steps",
        "",
        "## What was built",
        "",
        f"A set of **{len(tmpls)} production n8n workflows** that automate the end-to-end "
        "operational loop for an SEO / marketing services engagement:",
        "",
    ]
    for t in tmpls:
        lines.append(f"- **{pretty(t)}**")
    lines += [
        "",
        "## How it works",
        "",
        "- Workflows trigger from Microsoft Graph, email, or a slash command.",
        "- Each workflow is parameterized per-client via a `client_manifest.json` in the "
        "  monorepo — new clients inherit the full automation stack on onboarding.",
        "- Outputs flow into Teams/Planner for human review, not straight-to-client — the "
        "  automation handles the plumbing, humans own the judgment calls.",
        "",
        "## Outcomes",
        "",
        "- New-client onboarding: minutes, not days. Folder structure, agreements template, "
        "  initial audit, and workspace provisioning fire automatically.",
        "- Reporting cadence: weekly + monthly reports generated on schedule without a PM "
        "  chasing data.",
        "- Paid-media reporting: pulled from Google Ads API and delivered to the client's "
        "  inbox as a branded PDF.",
        "",
        "## Outreach-ready summary",
        "",
        "We don't sell 'an automation.' We sell a running ops backbone — 5 production n8n "
        "workflows handling onboarding, content pipeline, SEO reporting, paid-media "
        "reporting, and team training. It's the reason our SEO team can service 6+ clients "
        "with 4 people and still hit weekly cadence.",
        "",
    ]
    fpath = CAP_DIR / "n8n-workflow-automation.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return {"capability": "n8n Automation", "file": str(fpath.relative_to(CS_DIR))}


def build_capability_ppt_gen() -> dict:
    lines = [
        "# Automated Status-Review Deck Generation",
        "",
        "- **Capability:** Dev + Data-to-Presentation Automation",
        "- **Applies to:** Any agency or services firm delivering recurring client reviews",
        "",
        "## What was built",
        "",
        "A Python pipeline (`weekly_pipeline.py`, 63 KB orchestrator + a 117 KB PPT "
        "generator) that ingests raw metric exports (.docx from SEMrush / HOTH / GSC / GA4 "
        "/ OpenTable / PageSpeed) and emits a fully-branded, narrative-structured PPTX per "
        "client, per week — complete with speaker notes.",
        "",
        "## How it works",
        "",
        "- **Config-driven:** one `client_manifest.json` per client drives everything; a new "
        "  client slots into the pipeline with zero code changes.",
        "- **Metric catalog:** a shared learnings doc codifies what \"healthy\" looks like per "
        "  metric (GSC CTR, GA4 bounce rate, PageSpeed, SEMrush rank distribution, OpenTable "
        "  no-show rate, etc.) so narrative generation is consistent across clients.",
        "- **Outputs per run:** branded PPTX (6-section narrative), next-week ticket CSV "
        "  (auto-populated based on lowlights), structured metrics JSON for trend tracking.",
        "",
        "## Outcomes",
        "",
        "- A deck that took 4-6 hours manually now renders in under a minute.",
        "- Speaker notes are drafted — the SEO lead reviews and edits rather than writing from "
        "  scratch.",
        "- Next-week assignments flow out as a CSV, already routed to the right specialist "
        "  based on lowlight type (data-driven load balancing, not guesswork).",
        "",
        "## Outreach-ready summary",
        "",
        "Client status reviews shouldn't eat a day per client per week. We built a data-to-"
        "deck pipeline that handles everything from .docx metric intake to branded PowerPoint "
        "output with speaker notes — per client, per week, in under a minute each.",
        "",
    ]
    fpath = CAP_DIR / "ppt-pipeline-automation.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return {"capability": "PPT Pipeline", "file": str(fpath.relative_to(CS_DIR))}


def build_capability_video() -> dict:
    lines = [
        "# AI-Avatar Video Production at Scale",
        "",
        "- **Capability:** AI + Content Production",
        "- **Applies to:** Any industry investing in educational or social video content",
        "",
        "## What was built",
        "",
        "A HeyGen-based video production pipeline with a documented workaround for the "
        "MCP server's known Pydantic validation bugs. Produces branded avatar-driven explainer "
        "videos on demand from a script + avatar ID.",
        "",
        "## How it works",
        "",
        "- Secrets sourced from a user-local `apikeys/` folder (never in repo).",
        "- A monitor script polls the HeyGen job every 60 seconds, auto-downloads on `success`, "
        "  renames per the content calendar, and drops the file into the client's OneDrive "
        "  videos folder.",
        "- The Antigravity skill (`heygen_video_generation.md`) captures every gotcha we've "
        "  hit (avatar vs. avatar-group IDs, voice-ID validation, how to fall back to "
        "  PowerShell `Invoke-RestMethod` when MCP fails) — documented once, every future "
        "  run is fast.",
        "",
        "## Outcomes",
        "",
        "- Branded explainer videos on a weekly cadence (e.g., the \"2AM CyberBreach\" "
        "  security-awareness series), without a videographer.",
        "- Reusable across clients — swap avatar + script, keep the pipeline.",
        "",
        "## Outreach-ready summary",
        "",
        "We produce AI-avatar explainer videos on demand from a script — branded, on-brand, "
        "delivered weekly. Same economics as a YouTube short, same polish as a broadcast "
        "explainer.",
        "",
    ]
    fpath = CAP_DIR / "ai-avatar-video-pipeline.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return {"capability": "AI Video", "file": str(fpath.relative_to(CS_DIR))}


def build_capability_data_driven_team() -> dict:
    lines = [
        "# Data-Driven Team Allocation",
        "",
        "- **Capability:** Dev + Operations Intelligence",
        "- **Applies to:** Any services firm with 3+ specialists and per-engagement billing",
        "",
        "## What was built",
        "",
        "A Python analyzer (`seo_team_skills_analyzer.py`) that pulls 30 days of billing-"
        "level time entries from the Client Portal API (stored-procedure exec), tags each "
        "entry with a skill category (technical SEO, on-page, keyword research, WordPress, "
        "video, outreach, reporting), and emits a `seo_team_skills.md` document that "
        "answers, for every lowlight type: **first choice, second choice, third choice** "
        "specialist to assign.",
        "",
        "## How it works",
        "",
        "- Pulls time entries by UserID via `stp_xml_TicketDetail_TimeSheet_Detail_Get`.",
        "- Classifies each ticket into one of ~10 SEO skill buckets via keyword rules on "
        "  the title/notes.",
        "- Aggregates hours per person per skill; builds an assignment decision matrix.",
        "- Flags overload (> 40h / week sustained) so the planner raises it instead of "
        "  silently piling on.",
        "",
        "## Outcomes",
        "",
        "- Assignment decisions for weekly reviews are data-backed, not tribal.",
        "- The artifact refreshes every 4–6 weeks — the team's actual work (not their job "
        "  titles) drives who gets what.",
        "- Overload is visible in writing before it becomes a burnout or delivery problem.",
        "",
        "## Outreach-ready summary",
        "",
        "We read our own time-tracking data the way a CFO reads an income statement. Every "
        "4-6 weeks the skill matrix refreshes — each specialist's real hours by category "
        "drive assignment decisions. It's why our SEO delivery stays consistent as team "
        "composition shifts.",
        "",
    ]
    fpath = CAP_DIR / "data-driven-team-allocation.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return {"capability": "Team Ops", "file": str(fpath.relative_to(CS_DIR))}


# ---------- orchestration ----------

def main() -> int:
    if not SEO_REPO.exists():
        print(f"Clone not found at {SEO_REPO}", file=sys.stderr)
        return 1

    written: list[dict] = []
    for code in SEO_CLIENTS:
        r = build_client_case_study(code)
        if r:
            written.append(r)

    cap = [
        build_capability_ai_agents(),
        build_capability_n8n(),
        build_capability_ppt_gen(),
        build_capability_video(),
        build_capability_data_driven_team(),
    ]

    # Update index with a new section
    idx_path = CS_DIR / "_index.md"
    existing = idx_path.read_text(encoding="utf-8") if idx_path.exists() else ""
    existing = re.sub(r"\n# SEO, AI & Dev case studies.*\Z", "", existing, flags=re.S).rstrip()
    parts = [existing, "", "", "# SEO, AI & Dev case studies",
             "", "Drawn from the `technijian-seo/sdlc` repo (2026 work logs + agent / automation stack).",
             "", "## Per-industry SEO engagements", ""]
    by_ind: dict[str, list] = {}
    for w in written:
        by_ind.setdefault(w["industry"], []).append(w)
    for ind in sorted(by_ind):
        parts.append(f"### {ind}")
        for w in by_ind[ind]:
            parts.append(f"- [{w['file']}]({w['file']})")
        parts.append("")
    parts.append("## AI / Dev capabilities (cross-industry)")
    parts.append("")
    for c in cap:
        parts.append(f"- [{c['file']}]({c['file']}) — {c['capability']}")
    parts.append("")
    idx_path.write_text("\n".join(parts), encoding="utf-8")

    print(f"Wrote {len(written)} per-client SEO case studies + {len(cap)} capability case studies.")
    for w in written:
        print(f"  SEO    {w['industry']:20s}  {w['file']}")
    for c in cap:
        print(f"  CAP    {c['capability']:20s}  {c['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
