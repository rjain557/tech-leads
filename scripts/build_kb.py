"""Aggregate raw Client Portal data into per-client knowledge base markdown.

Inputs (under tracking/kb/raw/):
  clients.json, proposals.json, proposals_5yr.json,
  proposal_detail/{ProposalID}.json,
  work_progress_header.json, work_progress_detail.json,
  contracts.json

Outputs:
  tracking/kb/clients/{slug}.md           — one file per client (gitignored, full PII)
  tracking/kb/clients/_index.md           — browse by industry
  tracking/kb/cache/client_index.json     — structured summary for downstream tools
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
OUT = REPO / "tracking" / "kb" / "clients"
OUT.mkdir(parents=True, exist_ok=True)


def load(name: str):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s[:60] or "client"


def clean_html(s: str | None) -> str:
    if not s:
        return ""
    # HTML entities -> text, strip tags, collapse whitespace
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[\u00A0\u200B]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_iso(s):
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(s).split(".")[0])
    except Exception:
        return None


def main() -> int:
    clients = load("clients.json")
    industries = json.loads((CACHE / "client_industries.json").read_text(encoding="utf-8"))
    proposals_5y = load("proposals_5yr.json")
    contracts = load("contracts.json")
    wp_header = load("work_progress_header.json")
    wp_detail = load("work_progress_detail.json")

    detail_dir = RAW / "proposal_detail"

    # Index proposals by ClientID
    proposals_by_client: dict[int, list[dict]] = defaultdict(list)
    for p in proposals_5y:
        proposals_by_client[p["ClientID"]].append(p)

    # Index contracts by Client_ID
    contracts_by_client: dict[int, list[dict]] = defaultdict(list)
    for c in contracts:
        cid = c.get("Client_ID") or c.get("ClientID")
        if cid is not None:
            contracts_by_client[cid].append(c)

    # Index work-progress by proposal
    wp_header_by_pp = {h["ProjectProposalID"]: h for h in wp_header}
    wp_detail_by_pp: dict[int, list[dict]] = defaultdict(list)
    for d in wp_detail:
        wp_detail_by_pp[d.get("ProjectProposalId") or d.get("ProjectProposalID")].append(d)

    index_rows = []
    for c in clients:
        dir_id = c["DirID"]
        name = c["Location_Name"]
        industry = industries.get(str(dir_id), {}).get("industry", "Other")
        props = sorted(proposals_by_client.get(dir_id, []),
                       key=lambda p: p.get("ProjectDate") or "", reverse=True)
        conts = sorted(contracts_by_client.get(dir_id, []),
                       key=lambda x: x.get("StartDate") or x.get("From_Date") or "", reverse=True)

        slug = f"{dir_id}-{slugify(name)}"
        file = OUT / f"{slug}.md"

        active_contracts = [c for c in conts if c.get("Active") or c.get("Is_Active_Contract")]
        total_est_hrs = 0.0
        total_worked_hrs = 0.0
        for pp in props:
            h = wp_header_by_pp.get(pp["ProjectProposalID"])
            if h:
                total_est_hrs += float(h.get("TotalEstHr") or 0)
                total_worked_hrs += float(h.get("TotalHrWorked") or 0)

        lines = []
        lines.append(f"# {name}")
        lines.append("")
        lines.append(f"- **Industry:** {industry}")
        lines.append(f"- **DirID:** {dir_id}  |  **Code:** {c['LocationCode']}")
        created = parse_iso(c.get("CreateDateTime"))
        if created:
            lines.append(f"- **Client since:** {created.date().isoformat()}")
        lines.append(f"- **Net terms:** {c.get('Net_Terms','')}")
        lines.append(f"- **Proposals (5yr):** {len(props)}")
        lines.append(f"- **Contracts (all time):** {len(conts)}  (active: {len(active_contracts)})")
        if total_est_hrs or total_worked_hrs:
            lines.append(f"- **Estimated hrs (open work):** {total_est_hrs:.1f}  |  **Worked:** {total_worked_hrs:.1f}")
        lines.append("")

        # Active contracts
        if active_contracts:
            lines.append("## Active contracts")
            lines.append("")
            for ac in active_contracts[:20]:
                cname = ac.get("Contract_Name","")
                start = ac.get("StartDate") or ac.get("From_Date") or ""
                end = ac.get("EndDate") or ac.get("To_Date") or ""
                lines.append(f"- {cname}  ({str(start)[:10]} → {str(end)[:10]})")
            lines.append("")

        # Proposals (5yr) - summary table + detail expandable
        if props:
            lines.append("## Proposals (5-year window)")
            lines.append("")
            lines.append("| Date | Title | LinkedContract | Status |")
            lines.append("|------|-------|----------------|--------|")
            for p in props:
                date = str(p.get("ProjectDate") or "")[:10]
                title = (p.get("ProjectTitle") or "").replace("|","/")[:90]
                lc = p.get("LinkedContract") or ""
                status = p.get("Status") or ""
                lines.append(f"| {date} | {title} | {lc} | {status} |")
            lines.append("")

            lines.append("## Proposal detail")
            lines.append("")
            for p in props:
                pp = p["ProjectProposalID"]
                lines.append(f"### {pp} — {p.get('ProjectTitle','')}  ({str(p.get('ProjectDate') or '')[:10]})")
                desc = clean_html(p.get("ProjectDescription"))
                if desc:
                    lines.append("")
                    lines.append("**Client context (proposal description):**")
                    lines.append("")
                    lines.append(desc)
                    lines.append("")
                # Load detail if available
                dfile = detail_dir / f"{pp}.json"
                if dfile.exists():
                    d = json.loads(dfile.read_text(encoding="utf-8"))
                    needs = d.get("needs") or []
                    schedule = d.get("schedule") or []
                    for n in needs:
                        lines.append(f"**Need:** {n.get('NeedName','(unnamed)')}")
                        lines.append("")
                        for field in ("Description", "Solution", "Stratergy", "Objectives",
                                      "GeneralRequirements", "TechnicalReqirements",
                                      "ReportingMonitoring", "Assumption", "Evaluation"):
                            val = clean_html(n.get(field))
                            if val:
                                label = {"Stratergy":"Strategy",
                                         "TechnicalReqirements":"Technical Requirements",
                                         "ReportingMonitoring":"Reporting/Monitoring"}.get(field, field)
                                lines.append(f"- *{label}:* {val}")
                        hrs = n.get("PerHourCost") or 0
                        fp = n.get("FixedPriceCost") or 0
                        if hrs or fp:
                            lines.append(f"- *Pricing:* per-hour=${hrs}  fixed=${fp}")
                        lines.append("")
                    if schedule:
                        roles = defaultdict(float)
                        for s in schedule:
                            roles[s.get("RoleType","?")] += float(s.get("Esthours") or 0)
                        total_hrs = sum(roles.values())
                        lines.append(f"*Effort estimate:* {total_hrs:.1f} hrs across " +
                                     ", ".join(f"{r} ({h:.1f}h)" for r,h in roles.items()))
                        lines.append("")
                h = wp_header_by_pp.get(pp)
                if h:
                    lines.append(f"*Progress:* est {h.get('TotalEstHr',0)}h / worked {h.get('TotalHrWorked',0)}h  |  "
                                 f"expected end {str(h.get('ExpectedEndDate') or '')[:10]}  |  status {h.get('Status','?')}")
                    lines.append("")

        file.write_text("\n".join(lines), encoding="utf-8")
        index_rows.append({
            "slug": slug,
            "file": f"clients/{slug}.md",
            "DirID": dir_id,
            "LocationCode": c["LocationCode"],
            "Location_Name": name,
            "industry": industry,
            "proposals_5yr": len(props),
            "contracts_total": len(conts),
            "contracts_active": len(active_contracts),
            "worked_hrs": round(total_worked_hrs,1),
        })

    # Write index
    by_ind: dict[str, list] = defaultdict(list)
    for r in index_rows:
        by_ind[r["industry"]].append(r)

    idx = ["# Client KB — Index", "",
           f"Source: Client Portal API, {len(index_rows)} active clients",
           ""]
    for ind in sorted(by_ind):
        rs = sorted(by_ind[ind], key=lambda r: -r["proposals_5yr"])
        idx.append(f"## {ind}  ({len(rs)} clients)")
        idx.append("")
        for r in rs:
            idx.append(f"- [{r['Location_Name']}]({r['slug']}.md) — props5y:{r['proposals_5yr']} "
                       f"contracts:{r['contracts_active']}/{r['contracts_total']} "
                       f"workedHrs:{r['worked_hrs']}")
        idx.append("")
    (OUT / "_index.md").write_text("\n".join(idx), encoding="utf-8")
    (CACHE / "client_index.json").write_text(json.dumps(index_rows, indent=2), encoding="utf-8")

    print(f"Wrote {len(index_rows)} per-client KB files -> {OUT.relative_to(REPO)}/")
    print(f"Index -> clients/_index.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
