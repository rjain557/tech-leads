"""Classify each active client into an industry bucket using name + proposal text.

Rule-based heuristic, tuned to Technijian's current client mix. Manual
overrides live in tracking/kb/cache/client_industries.json — if a
classification is wrong, edit that file directly and it will be preserved
on re-run (only first-time classifications are filled in).

Industries used:
  Legal, Healthcare, Financial Services, Construction,
  Manufacturing, Hospitality, Real Estate / Property Mgmt,
  Professional Services, Engineering, Logistics, Automotive,
  Technology, Non-Profit, Other
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "tracking" / "kb" / "raw"
CACHE = REPO / "tracking" / "kb" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = CACHE / "client_industries.json"

RULES = [
    ("Legal",                   [r"\blaw\b", r"\battorneys?\b", r"law firm", r"law offices?", r"\blegal\b"]),
    ("Healthcare",              [r"\bmd\b", r"\bmd,?\s*pc\b", r"medical", r"medicine", r"clinic", r"dental", r"endodontic",
                                 r"ortho\w*", r"pediatric", r"surgery", r"hospital", r"pharmacy", r"veterinary", r"pet care"]),
    ("Financial Services",      [r"financial", r"finance", r"advisor", r"advisory", r"wealth", r"capital",
                                 r"lending", r"insurance", r"benefits", r"investment", r"fund", r"bank",
                                 r"cpa", r"accounting", r"tax"]),
    ("Construction",            [r"construction", r"\bhomes?\b", r"builder", r"interiors?", r"tile",
                                 r"stone", r"flooring", r"roofing", r"hvac", r"plumbing", r"electrical contractor",
                                 r"general contractor", r"remodel"]),
    ("Manufacturing",           [r"manufactur\w*", r"\bmfg\b", r"industries", r"industrial", r"\baero\b",
                                 r"aerospace", r"silicon", r"semiconductor", r"container", r"controls",
                                 r"\bspec\b", r"magnespec", r"bromic"]),
    ("Hospitality",             [r"hotel", r"\bspa\b", r"resort", r"restaurant", r"dining", r"hospitality", r"winery", r"cafe"]),
    ("Real Estate / Property",  [r"apartment", r"property management", r"realty", r"\breal estate\b",
                                 r"leasing", r"rentals?", r"homeowners", r"hoa", r"foundation\b.*community"]),
    ("Engineering",             [r"engineering", r"\beng\b", r"consulting engineers?"]),
    ("Logistics",               [r"shipping", r"logistics", r"freight", r"air services", r"transport"]),
    ("Automotive",              [r"automotive", r"\bauto\b", r"autosports", r"dealerships?", r"motor"]),
    ("Marketing / Advertising", [r"marketing", r"advertising", r"ad agency", r"\bpr\b", r"branding"]),
    ("Technology",              [r"\bit services\b", r"software", r"solutions inc", r"technology", r"\bai\b", r"tech\b"]),
    ("Non-Profit",              [r"foundation", r"non.?profit", r"ministry", r"housing for health", r"\boneoc\b",
                                 r"apartment association"]),
    ("Professional Services",   [r"consulting", r"advisors? group", r"group inc", r"associates",
                                 r"talent solutions", r"staffing"]),
]


def classify_name(name: str) -> str | None:
    low = name.lower()
    for label, patterns in RULES:
        for pat in patterns:
            if re.search(pat, low):
                return label
    return None


def load_existing() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def proposal_text_by_client() -> dict[int, str]:
    p = RAW / "proposals.json"
    if not p.exists():
        return {}
    props = json.loads(p.read_text(encoding="utf-8"))
    by_client: dict[int, list[str]] = {}
    for pr in props:
        cid = pr.get("ClientID")
        if cid is None:
            continue
        parts = [pr.get("ProjectTitle") or "", pr.get("ProjectDescription") or ""]
        by_client.setdefault(cid, []).extend(parts)
    return {k: "\n".join(v).lower() for k, v in by_client.items()}


def main() -> int:
    clients = json.loads((RAW / "clients.json").read_text(encoding="utf-8"))
    existing = load_existing()
    ptext = proposal_text_by_client()

    results = {}
    for c in clients:
        key = str(c["DirID"])
        name = c["Location_Name"]
        if key in existing and existing[key].get("manual"):
            results[key] = existing[key]
            continue
        # 1) Name rules
        industry = classify_name(name)
        # 2) Fallback: scan proposal text for industry cues
        if industry is None:
            blob = ptext.get(c["DirID"], "")
            industry = classify_name(blob) or "Other"
        results[key] = {
            "DirID": c["DirID"],
            "LocationCode": c["LocationCode"],
            "Location_Name": name,
            "industry": industry,
            "manual": existing.get(key, {}).get("manual", False),
        }

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Print a summary by industry
    tally: dict[str, int] = {}
    for r in results.values():
        tally[r["industry"]] = tally.get(r["industry"], 0) + 1
    print(f"{len(results)} clients classified:")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    print(f"\n  cache -> {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
