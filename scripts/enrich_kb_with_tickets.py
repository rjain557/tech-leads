"""Enrich the knowledge base with 12-month ticket + time-entry data.

Reads per-client ticket JSON from tracking/kb/raw/ticket_timeentry/*.json.
For each ticket entry (WorkPeriod row) we:

  1. Strip HTML so keyword matching works on real text
  2. Classify into a service theme (AI, dev, SEO, network, etc.)
  3. Aggregate at two levels:
       - per client  -> update tracking/kb/clients/{slug}.md with a
           "Ticket activity (12mo)" section
       - per industry x theme -> generate additional anonymized case
           studies in tracking/kb/case-studies/{industry}/ticket-{theme}.md

Ticket case studies describe the BODY of work done for an industry, not
a single proposal. They complement the proposal-driven case studies.
"""
from __future__ import annotations
import html
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "tracking" / "kb" / "raw" / "ticket_timeentry"
CACHE = REPO / "tracking" / "kb" / "cache"
CLIENTS_DIR = REPO / "tracking" / "kb" / "clients"
CS_DIR = REPO / "tracking" / "kb" / "case-studies"


# ------- HTML / markup strip (ticket notes are messy: ChatGPT pastes, OWA replies, etc.) -------

_TAG_RE = re.compile(r"<[^>]+>")
_UNCLOSED_TAG_FRAG = re.compile(r"[a-z-]+=\"[^\"]*\"\s*>?|\s*>", re.I)
_CHATGPT_ATTR_RESIDUE = re.compile(
    # Chunks that survive tag-strip because they were inside attribute values
    # e.g. `*]:pointer-events-auto scroll-mt-[calc(var(...))]"` or data-turn-id residue
    r"(?:\*\]:[^\s\"']+|data-[a-z-]+=\"[^\"]*\"|scroll-mt-\[[^\]]*\]|scroll-mt-\([^)]*\)|"
    r"calc\([^)]*\)|pointer-events-[a-z-]+|min\([^)]*\)|max\([^)]*\)|"
    r"-?-?(?:header|shadow)-[a-z-]+|text-token-[a-z-]+|dir=\"auto\")",
    re.I,
)


def clean_note(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = _TAG_RE.sub(" ", s)
    s = _CHATGPT_ATTR_RESIDUE.sub(" ", s)
    # A second pass catches leftover `attr="value">` fragments from malformed tags
    s = _UNCLOSED_TAG_FRAG.sub(" ", s)
    s = s.replace("\u00A0", " ").replace("\u200B", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ------- theme rules (distinct from proposal themes -- ticket work has different shape) -------

TICKET_THEMES = [
    ("ai-automation",       ["chatgpt", "openai", "claude", " llm ", " gpt ", "copilot", "anthropic",
                             "prompt engineering", "ai workflow", "langchain", "ai integration",
                             "artificial intelligence", "machine learning", "computer vision", "rag pipeline"]),
    ("custom-dev",          ["custom script", "python script", "powershell script", "api integration",
                             "react app", "node.js", "node js", "wrote script", "built a tool",
                             "custom code", "developed a", "dev work", "automation script", "webhook",
                             "rest api", "graphql"]),
    ("seo-marketing",       [" seo ", "search engine optimization", "google ads", "adwords", "keyword research",
                             "schema markup", "backlink", "meta description", "seo audit"]),
    ("website-work",        ["wordpress", "landing page", "website redesign", "web form", "ssl certificate",
                             "domain transfer", "dns setup"]),
    ("voip-telephony",      ["3cx", " voip", "phone system", "sip trunk", "extension", "ring group",
                             "call queue", "auto attendant", "ip phone", "sip provider"]),
    ("m365-admin",          ["microsoft 365", "m365", "exchange online", "sharepoint", "onedrive",
                             "teams admin", "intune", "entra id", "azure ad", "mfa setup", "conditional access"]),
    ("backup-recovery",     ["veeam", "backup job", "restore from backup", "disaster recovery", "bcdr"]),
    ("security-incident",   ["phishing email", "malware", "ransomware", "security incident",
                             "compromised account", "password reset all", "incident response"]),
    ("network-infra",       ["firewall", "sophos", "sonicwall", "fortigate", "vlan", "switch config",
                             "wireless ap", "site-to-site vpn", "vpn client"]),
    ("endpoint-mgmt",       ["endpoint", "edr", "defender", "sentinelone", "crowdstrike", "windows update",
                             "driver install", "gpo ", "group policy"]),
    ("email-deliverability",["dmarc", "dkim", " spf ", "mx record", "spam filter", "proofpoint", "mimecast"]),
    ("server-admin",        ["windows server", "active directory", "domain controller", "hyper-v",
                             "vmware", "esxi", "server 2019", "server 2022"]),
    ("printer-hardware",    ["printer", "print driver", "print queue", "toner"]),
    ("user-onboarding",     ["new hire", "new user setup", "offboarding", "account setup",
                             "onboarding", "license assignment"]),
    ("helpdesk-misc",       ["password reset", "unlock account", "login issue", "forgot password"]),
]

GENERIC_TICKET_THEME = "general-support"


def theme_for(note: str) -> str:
    low = note.lower()
    for label, kws in TICKET_THEMES:
        for kw in kws:
            if kw in low:
                return label
    return GENERIC_TICKET_THEME


# ------- aggregation -------

def parse_time_to_hours(s: str) -> float:
    """Parse 'HH:MM AM - HH:MM PM' into decimal hours. Returns 0 on fail."""
    if not s:
        return 0.0
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP]M)?\s*[-to]+\s*(\d{1,2}):(\d{2})\s*([AP]M)?", s, re.I)
    if not m:
        return 0.0
    try:
        h1, mn1, ap1, h2, mn2, ap2 = m.groups()
        def to_24(h, ap):
            h = int(h)
            if ap and ap.upper() == "PM" and h != 12: h += 12
            if ap and ap.upper() == "AM" and h == 12: h = 0
            return h
        start = to_24(h1, ap1) * 60 + int(mn1)
        end   = to_24(h2, ap2) * 60 + int(mn2)
        if end < start:
            end += 24 * 60
        return (end - start) / 60.0
    except Exception:
        return 0.0


def load_industries() -> dict[int, str]:
    d = json.loads((CACHE / "client_industries.json").read_text(encoding="utf-8"))
    return {v["DirID"]: v["industry"] for v in d.values()}


def main() -> int:
    if not RAW.exists():
        print("No ticket_timeentry data - run fetch_tickets_timeentries.py first", flush=True)
        return 1
    industries = load_industries()
    # Per-client rows with cleaned note + theme + hours
    per_client: dict[int, list[dict]] = {}
    for f in sorted(RAW.iterdir()):
        if not f.name.endswith(".json"):
            continue
        cid = int(f.stem)
        rows = json.loads(f.read_text(encoding="utf-8"))
        proc = []
        for r in rows:
            note = clean_note(r.get("TktEntryNote"))
            theme = theme_for(note)
            hrs = parse_time_to_hours(r.get("WorkPeriodTime") or "")
            proc.append({
                "TicketID": r.get("TicketID"),
                "TktCreateDate": r.get("TktCreateDate"),
                "WorkPeriodDate": r.get("WorkPeriodDate"),
                "Employee": r.get("Employee"),
                "Note": note,
                "Theme": theme,
                "Hours": round(hrs, 2),
            })
        per_client[cid] = proc

    # Write cleaned per-client data (gitignored)
    (CACHE / "ticket_timeentry_clean").mkdir(exist_ok=True)
    for cid, rows in per_client.items():
        (CACHE / "ticket_timeentry_clean" / f"{cid}.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8")

    # ----- Append per-client KB summary -----
    for client_md in CLIENTS_DIR.glob("*.md"):
        if client_md.name == "_index.md":
            continue
        m = re.match(r"^(\d+)-", client_md.name)
        if not m:
            continue
        cid = int(m.group(1))
        rows = per_client.get(cid, [])
        if not rows:
            continue
        # Only rewrite if not already enriched
        content = client_md.read_text(encoding="utf-8")
        content = re.sub(r"\n## Ticket activity \(12mo\).*\Z", "", content, flags=re.S).rstrip()

        by_theme = defaultdict(lambda: {"rows":0,"hours":0.0,"tickets":set(),"notes":[]})
        for r in rows:
            b = by_theme[r["Theme"]]
            b["rows"] += 1
            b["hours"] += r["Hours"]
            b["tickets"].add(r["TicketID"])
            if len(b["notes"]) < 5 and r["Note"]:
                b["notes"].append(r["Note"][:300])

        parts = ["", "## Ticket activity (12mo)", ""]
        parts.append(f"**Total:** {len(rows)} work periods across "
                     f"{len({r['TicketID'] for r in rows})} tickets, "
                     f"~{sum(r['Hours'] for r in rows):.1f} hrs")
        parts.append("")
        parts.append("| Theme | Tickets | Rows | Hours |")
        parts.append("|-------|---------|------|-------|")
        for t, b in sorted(by_theme.items(), key=lambda x: -x[1]["hours"]):
            parts.append(f"| {t} | {len(b['tickets'])} | {b['rows']} | {b['hours']:.1f} |")
        parts.append("")
        # Sample notes for the top 3 themes
        for t, b in sorted(by_theme.items(), key=lambda x: -x[1]["hours"])[:3]:
            if not b["notes"]:
                continue
            parts.append(f"### Sample work — {t}")
            parts.append("")
            for n in b["notes"]:
                parts.append(f"- {n}")
            parts.append("")
        client_md.write_text(content + "\n" + "\n".join(parts), encoding="utf-8")

    # ----- Generate ticket-driven case studies by industry x theme -----
    # Collect rows grouped by industry then theme
    by_ind_theme: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for cid, rows in per_client.items():
        ind = industries.get(cid, "Other")
        for r in rows:
            if not r["Note"]:
                continue
            by_ind_theme[ind][r["Theme"]].append(r)

    # Aliases per client for scrubbing (we need client name + code for this)
    clients_json = json.loads((REPO / "tracking/kb/raw/clients.json").read_text(encoding="utf-8"))
    name_by_cid = {c["DirID"]: c["Location_Name"] for c in clients_json}
    code_by_cid = {c["DirID"]: c["LocationCode"] for c in clients_json}

    from build_case_studies import derive_aliases, scrub  # reuse the existing scrubber

    # Global alias pool so cross-client name leaks in notes are caught.
    # Exclude very short/ambiguous tokens to avoid scrubbing generic words.
    global_aliases: set[str] = set()
    for c in clients_json:
        for a in derive_aliases(c["Location_Name"], c["LocationCode"]):
            if len(a) >= 5:  # skip short codes that could match common words
                global_aliases.add(a)
    global_aliases_sorted = sorted(global_aliases, key=len, reverse=True)

    MIN_TICKETS = 2   # don't generate a case-study from a single ticket
    written_cs = []
    for ind, themes in by_ind_theme.items():
        for theme, rows in themes.items():
            if theme in ("helpdesk-misc", "printer-hardware", "user-onboarding", GENERIC_TICKET_THEME):
                continue  # skip pure helpdesk themes for case studies
            ticket_ids = {r["TicketID"] for r in rows}
            if len(ticket_ids) < MIN_TICKETS:
                continue

            total_hours = sum(r["Hours"] for r in rows)
            # Scrub sample notes. We need per-row aliases because each row
            # comes from a different client; walk rows + resolve cid.
            cid_for_row = {}
            for cid, rr in per_client.items():
                for r in rr:
                    if r in rows:  # identity check is stable within list
                        cid_for_row[id(r)] = cid

            samples = []
            for r in sorted(rows, key=lambda x: -x["Hours"])[:8]:
                cid = cid_for_row.get(id(r))
                if cid is None:
                    continue
                # Own-client aliases first (highest priority), then all other clients
                own = derive_aliases(name_by_cid[cid], code_by_cid[cid])
                combined = list(dict.fromkeys(own + global_aliases_sorted))
                note = scrub(r["Note"], combined, ind)
                if note:
                    samples.append((r["WorkPeriodDate"], r["Hours"], note[:500]))

            if not samples:
                continue

            fname = f"ticket-{theme}.md"
            ind_dir = CS_DIR / ind.lower().replace("/","-").replace(" ","-")
            ind_dir.mkdir(parents=True, exist_ok=True)
            fpath = ind_dir / fname

            lines = [f"# {ind} — {theme.replace('-',' ').title()} (ticket-driven)", ""]
            lines.append(f"- **Industry:** {ind}")
            lines.append(f"- **Service theme:** {theme}")
            lines.append(f"- **Source:** 12-month ticket + time-entry data")
            lines.append(f"- **Tickets:** {len(ticket_ids)}  |  **Work periods:** {len(rows)}  |  **~Hours:** {total_hours:.1f}")
            lines.append("")
            lines.append("## Representative work (anonymized)")
            lines.append("")
            for date, hrs, note in samples:
                lines.append(f"- **{date}  ({hrs:.1f}h)** — {note}")
            lines.append("")
            fpath.write_text("\n".join(lines), encoding="utf-8")
            written_cs.append({"industry": ind, "theme": theme, "tickets": len(ticket_ids), "hours": round(total_hours,1)})

    # Update case-study index - append a section
    idx_path = CS_DIR / "_index.md"
    existing = idx_path.read_text(encoding="utf-8") if idx_path.exists() else ""
    # Strip previous ticket-driven block if present
    existing = re.sub(r"\n# Ticket-driven case studies.*\Z", "", existing, flags=re.S).rstrip()
    parts = [existing, "", "", "# Ticket-driven case studies", "",
             f"{len(written_cs)} additional case studies assembled from 12mo ticket + time-entry activity.", ""]
    by_ind: dict[str, list] = defaultdict(list)
    for w in written_cs:
        by_ind[w["industry"]].append(w)
    for ind in sorted(by_ind):
        parts.append(f"## {ind}")
        parts.append("")
        for w in sorted(by_ind[ind], key=lambda x: -x["hours"]):
            slug = ind.lower().replace('/','-').replace(' ','-')
            parts.append(f"- [{slug}/ticket-{w['theme']}.md]({slug}/ticket-{w['theme']}.md) — {w['tickets']} tickets, {w['hours']}h")
        parts.append("")
    idx_path.write_text("\n".join(parts), encoding="utf-8")

    print(f"Enriched {sum(1 for c in per_client if per_client[c])} client KB files.")
    print(f"Wrote {len(written_cs)} ticket-driven case studies.")
    print("\nTop ticket-driven case studies by hours:")
    for w in sorted(written_cs, key=lambda x: -x['hours'])[:15]:
        print(f"  {w['hours']:6.1f}h  {w['industry']:28s}  {w['theme']:25s}  ({w['tickets']} tickets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
