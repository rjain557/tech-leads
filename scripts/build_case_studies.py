"""Build industry-anonymized case studies from per-proposal data.

For each proposal:
  1. Classify into a "service theme" (network security, cloud migration, etc.)
      using keyword rules against title + needs text.
  2. Scrub client-identifying text (full name, common abbreviations,
      LocationCode, derived parenthetical short forms).
  3. Write a self-contained case-study markdown under
        tracking/kb/case-studies/{industry}/{theme}-{pp-id}.md

Also writes a top-level _index.md grouped by industry -> theme.

Output is safe to commit (industry + generic descriptors only).
"""
from __future__ import annotations
import html
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "tracking" / "kb" / "raw"
CACHE = REPO / "tracking" / "kb" / "cache"
OUT = REPO / "tracking" / "kb" / "case-studies"
OUT.mkdir(parents=True, exist_ok=True)


# ---------- service themes ----------

THEMES = [
    ("voip-telephony",          ["3cx", "voip", "phone system", "pbx", "sip trunk", "telephony", "ringcentral"]),
    ("network-security",        ["firewall", "sophos", "fortinet", "ids", "ips", "edge appliance", "network security", "vpn ", "site-to-site", "sslvpn", "sonicwall"]),
    ("wireless",                ["wireless", "wifi", "wi-fi", "wlan", "wirelessap", "access point", "meraki", "aruba", "unifi"]),
    ("workstation-lifecycle",   ["windows 10", "windows 11", "workstation upgrade", "pc refresh", "laptop refresh", "os upgrade", "os migration"]),
    ("microsoft-365",           ["m365", "microsoft 365", "o365", "office 365", "exchange online", "sharepoint", "onedrive", "teams migration", "intune"]),
    ("email-migration",         ["email migration", "mail migration", "imap migration", "exchange migration", "tenant migration"]),
    ("cloud-migration",         ["azure", " aws ", " gcp ", "cloud migration", "lift and shift", "cloud infrastructure"]),
    ("backup-continuity",       ["backup solution", "veeam", "disaster recovery", "business continuity", "bcp ", "rto ", "rpo ", "backup server", "immutable backup"]),
    ("server-infrastructure",   ["server upgrade", "windows server", "active directory", "domain controller", "hyper-v", "vmware", "esxi", "virtualization"]),
    ("hipaa-compliance",        ["hipaa", "protected health information", " phi ", "hitrust"]),
    ("soc2-compliance",         ["soc 2", "soc2", "soc ii"]),
    ("cmmc-compliance",         ["cmmc", "controlled unclassified information", "cui ", "nist 800-171"]),
    ("finance-compliance",      ["finra", "sec regulation", "reg s-p", "reg s-id", " gramm", " glba", "pci-dss"]),
    ("security-assessment",     ["penetration test", "pen test", "security assessment", "vulnerability assess", "risk assessment", "gap assessment"]),
    ("email-security",          ["proofpoint", "mimecast", "email security", "phishing protection", "dmarc", "dkim", " spf "]),
    ("endpoint-security",       ["endpoint", " edr ", " xdr ", "sentinelone", "crowdstrike", "defender", "antivirus"]),
    ("mdm-device-mgmt",         [" mdm", "mobile device", "device management"]),
    ("custom-software",         ["web application", "custom application", "portal development", "api integration", "database update", "application modification"]),
    ("business-applications",   ["quickbooks", "qb merge", " crm ", "customer relationship management", " erp ", "salesforce", "netsuite", "line-of-business"]),
    ("storage-hardware",        [" nas ", " san ", "synology", "qnap", "storage upgrade"]),
    ("power-physical",          [" ups ", "battery backup", "surge protection", "cabling", "rack install"]),
    ("ai-automation",           ["artificial intelligence", " ai ", "machine learning", "automation", "copilot", "chatgpt"]),
    ("it-managed-services",     ["managed services", " msp ", "help desk", "it support", "sla ", "24/7 monitoring"]),
    ("website-seo",             [" seo ", "google ads", "website redesign", "search engine optimization"]),
    ("ticket-transition",       ["onboarding", "transition", "kickoff", "initial setup"]),
]

GENERIC_THEME = "general-it"


def detect_theme(title: str, body: str) -> str:
    """Title wins first; fall back to body. Title hits are weighted higher
    because titles describe the engagement, not incidental mentions."""
    t = (title or "").lower()
    b = (body or "").lower()
    for label, kws in THEMES:
        for kw in kws:
            if kw in t:
                return label
    for label, kws in THEMES:
        for kw in kws:
            if kw in b:
                return label
    return GENERIC_THEME


# ---------- scrubbing ----------

def derive_aliases(full_name: str, code: str) -> list[str]:
    aliases = {full_name, full_name.strip()}
    # Strip legal suffixes
    stripped = re.sub(r",?\s*(LLC|Inc\.?|L\.?P\.?|PC|P\.C\.|Corp\.?|Corporation|Co\.?|LLP|Ltd\.?|Company|Group)\s*$",
                      "", full_name, flags=re.I).strip()
    if stripped and stripped != full_name:
        aliases.add(stripped)
    # First word (often the brand)
    tokens = re.split(r"\s+", stripped)
    if tokens and len(tokens[0]) >= 4 and tokens[0].isalpha():
        aliases.add(tokens[0])
    # First two words
    if len(tokens) >= 2:
        aliases.add(" ".join(tokens[:2]))
    # Concatenated-name forms (no spaces/punctuation) — used as domains / handles
    concat = re.sub(r"[^A-Za-z0-9]", "", stripped)
    if len(concat) >= 6:
        aliases.add(concat)
    if code and len(code) >= 2:
        aliases.add(code)
    # Sort longest first so we replace full names before shorter overlaps
    return sorted({a for a in aliases if len(a) >= 3}, key=len, reverse=True)


def scrub(text: str, aliases: list[str], industry: str) -> str:
    if not text:
        return ""
    # Remove common inline parenthetical alias defs like ("AFFG")
    # Replace client-specific aliases with generic noun.
    replacement = {
        "Legal":                   "the firm",
        "Healthcare":              "the practice",
        "Financial Services":      "the firm",
        "Construction":            "the contractor",
        "Manufacturing":           "the manufacturer",
        "Hospitality":             "the property",
        "Real Estate / Property":  "the property management company",
        "Engineering":             "the firm",
        "Logistics":               "the logistics provider",
        "Automotive":              "the dealer group",
        "Marketing / Advertising": "the agency",
        "Technology":              "the company",
        "Non-Profit":              "the organization",
        "Professional Services":   "the firm",
        "Other":                   "the client",
    }.get(industry, "the client")
    # HTML/entity cleanup first so subsequent regexes see straight punctuation
    out = html.unescape(text)
    out = re.sub(r"<br\s*/?>", "\n", out, flags=re.I)
    out = re.sub(r"<[^>]+>", "", out)
    out = re.sub(r"[\u00A0\u200B]+", " ", out)

    for a in aliases:
        if not a:
            continue
        pat = r"\b" + re.escape(a) + r"\b"
        # Short all-caps codes (e.g. "FOR", "TOR", "ORX", "CSS") collide with
        # English words if matched case-insensitively. Match case-sensitively.
        if len(a) <= 4 and a.isupper() and a.isalpha():
            out = re.sub(pat, replacement, out)
        else:
            out = re.sub(pat, replacement, out, flags=re.I)

    # Scrub email-address local-parts + domain stems that contain an alias.
    # e.g. booking@orthoxpress.com -> booking@<redacted>.com
    def _email_sub(m):
        local, domain = m.group(1), m.group(2)
        low = (local + "@" + domain).lower()
        for a in aliases:
            al = a.lower().replace(" ", "")
            if len(al) >= 4 and al in low:
                return f"{local}@<redacted>"
        return m.group(0)
    out = re.sub(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", _email_sub, out)

    # Collapse redundant alias-definition parentheticals:
    #   the firm ("the firm")  |  the firm (\u201Cthe firm\u201D)  |  the firm ('the firm')
    quoted = re.escape(replacement)
    out = re.sub(
        rf"{quoted}\s*\(\s*[\"'\u201C\u2018]*\s*{quoted}\s*[\"'\u201D\u2019]*\s*\)",
        replacement, out, flags=re.I,
    )
    # Collapse "the the firm" / "The the firm" -> "the firm" / "The firm"
    if replacement.startswith("the "):
        short = replacement[4:]  # e.g. "firm"
        out = re.sub(rf"\bthe\s+the\s+{re.escape(short)}\b", replacement, out, flags=re.I)
    # Strip Docusign envelope IDs
    out = re.sub(r"Docusign Envelope ID:\s*[A-F0-9-]+", "", out, flags=re.I)
    # Capitalize sentence-start "the <x>"
    out = re.sub(rf"(^|[.!?]\s+){replacement}", lambda m: m.group(1) + replacement.capitalize(), out)
    out = re.sub(r" {2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# ---------- build ----------

def load(name: str):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def main() -> int:
    clients = {c["DirID"]: c for c in load("clients.json")}
    industries = json.loads((CACHE / "client_industries.json").read_text(encoding="utf-8"))
    proposals = load("proposals_5yr.json")
    wp_header = {h["ProjectProposalID"]: h for h in load("work_progress_header.json")}
    detail_dir = RAW / "proposal_detail"

    # Global alias pool: reused proposal templates sometimes reference
    # other clients by name. Include every client's aliases at scrub time.
    global_aliases: set[str] = set()
    for c in clients.values():
        for a in derive_aliases(c["Location_Name"], c["LocationCode"]):
            if len(a) >= 5:
                global_aliases.add(a)
    global_aliases_sorted = sorted(global_aliases, key=len, reverse=True)

    written = []
    for p in proposals:
        pp = p["ProjectProposalID"]
        cid = p["ClientID"]
        client = clients.get(cid)
        if not client:
            continue
        industry = industries.get(str(cid), {}).get("industry", "Other")
        own_aliases = derive_aliases(client["Location_Name"], client["LocationCode"])
        aliases = list(dict.fromkeys(own_aliases + global_aliases_sorted))

        title = p.get("ProjectTitle") or "Untitled"
        description = p.get("ProjectDescription") or ""

        needs = []
        schedule = []
        dfile = detail_dir / f"{pp}.json"
        if dfile.exists():
            d = json.loads(dfile.read_text(encoding="utf-8"))
            needs = d.get("needs") or []
            schedule = d.get("schedule") or []

        # Build the theme-detection blob
        body_blob = " ".join([description] +
                             [f"{n.get('NeedName','')} {n.get('Description','')} {n.get('Solution','')}" for n in needs])
        theme = detect_theme(title, body_blob)

        # Scrub title
        clean_title = scrub(title, aliases, industry)
        clean_desc = scrub(description, aliases, industry)

        # Effort total
        total_hrs = 0.0
        role_totals = defaultdict(float)
        for s in schedule:
            h = float(s.get("Esthours") or 0)
            total_hrs += h
            role_totals[str(s.get("RoleType","?"))] += h
        # Work progress (actuals)
        wp = wp_header.get(pp)

        # Write file
        ind_dir = OUT / industry.lower().replace("/", "-").replace(" ", "-")
        ind_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{theme}-{pp}.md"
        fpath = ind_dir / fname

        date = str(p.get("ProjectDate") or "")[:10]

        lines = []
        lines.append(f"# {clean_title}")
        lines.append("")
        lines.append(f"- **Industry:** {industry}")
        lines.append(f"- **Service theme:** {theme}")
        lines.append(f"- **Engagement date:** {date}")
        if total_hrs:
            lines.append(f"- **Estimated effort:** {total_hrs:.0f} hrs " +
                         ("(" + ", ".join(f"{r}: {h:.0f}h" for r,h in role_totals.items()) + ")" if role_totals else ""))
        if wp:
            lines.append(f"- **Delivered hrs:** {wp.get('TotalHrWorked',0)} (against {wp.get('TotalEstHr',0)} est)")
        lines.append("")

        if clean_desc:
            lines.append("## Client context")
            lines.append("")
            lines.append(clean_desc)
            lines.append("")

        populated_needs = []
        for n in needs:
            rendered = []
            for field, label in [
                ("Description","Problem / context"),
                ("Solution","Solution"),
                ("Stratergy","Strategy"),
                ("Objectives","Objectives"),
                ("GeneralRequirements","General requirements"),
                ("TechnicalReqirements","Technical requirements"),
                ("ReportingMonitoring","Reporting & monitoring"),
                ("Assumption","Assumptions"),
                ("Evaluation","Success criteria"),
            ]:
                val = scrub(n.get(field) or "", aliases, industry)
                if val:
                    rendered.append((label, val))
            if rendered:
                populated_needs.append((scrub(n.get("NeedName","(unnamed phase)"), aliases, industry), rendered))
        if populated_needs:
            lines.append("## Scope of work")
            lines.append("")
            for nm, rendered in populated_needs:
                lines.append(f"### {nm}")
                lines.append("")
                for label, val in rendered:
                    lines.append(f"**{label}:**")
                    lines.append("")
                    lines.append(val)
                    lines.append("")

        # Sales-ready summary for outreach templates
        lines.append("## Outreach-ready summary")
        lines.append("")
        gist = scrub((needs[0].get("Solution") if needs else "") or description, aliases, industry)
        gist = (gist[:400] + "…") if len(gist) > 400 else gist
        lines.append(gist or "_(no solution text captured)_")
        lines.append("")

        fpath.write_text("\n".join(lines), encoding="utf-8")
        written.append({
            "industry": industry, "theme": theme, "file": str(fpath.relative_to(OUT)),
            "proposal_id": pp, "date": date, "hours_est": round(total_hrs,1),
        })

    # Index grouped by industry -> theme
    by_ind: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for w in written:
        by_ind[w["industry"]][w["theme"]].append(w)

    idx = ["# Case Studies — Industry Index", "",
           f"{len(written)} anonymized case studies generated from Client Portal proposals (5-yr window).",
           "",
           "All client-identifying text has been replaced with industry-appropriate generic phrasing.",
           ""]
    for ind in sorted(by_ind):
        idx.append(f"## {ind}")
        idx.append("")
        for theme in sorted(by_ind[ind]):
            rs = sorted(by_ind[ind][theme], key=lambda r: r["date"] or "", reverse=True)
            idx.append(f"### {theme}  ({len(rs)})")
            for r in rs:
                idx.append(f"- [{r['file']}]({r['file']}) — {r['date']}  ({r['hours_est']}h)")
            idx.append("")
    (OUT / "_index.md").write_text("\n".join(idx), encoding="utf-8")

    print(f"Wrote {len(written)} case studies -> {OUT.relative_to(REPO)}/")
    # Theme tally
    tally = defaultdict(int)
    for w in written:
        tally[w["theme"]] += 1
    print("\nBy theme:")
    for t, n in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {n:3d}  {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
