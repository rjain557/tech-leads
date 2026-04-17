"""Pull knowledge-base source data from the Client Portal API.

Strategy (revised after SP probe):
  1. List 67 active clients          -> /api/clients/active (stp_Active_Clients)
  2. Pull 499 proposals (5yr scope)  -> GET_PROPOSALS_LIST filter by ProjectDate
  3. Pull 206 work-progress rows     -> stp_Get_Peoposal_Work_Progress_List
  4. Pull 1610 contracts             -> GetAllContracts
  5. Pull per-proposal detail        -> stp_Get_Project_Proposal for each (needs + schedule)
     (needs table = problem / solution / strategy / objectives / tech requirements)

Tickets / time entries: deliberately skipped for this pass.
  - Ticket SPs probed either require an authorized UserID > 0 or return
    0 rows for our session. Case-study narrative material already lives
    in proposals + proposal-needs + work-progress.

All raw JSON lands under tracking/kb/raw/ (gitignored).
"""
from __future__ import annotations
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client_portal import ClientPortal, REPO

RAW = REPO / "tracking" / "kb" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

NOW = datetime.now()
FIVE_YR_CUTOFF = NOW - timedelta(days=365 * 5)
ONE_YR_CUTOFF = NOW - timedelta(days=365)


def first_rows(result: dict, set_index: int = 0) -> list[dict]:
    """Robust extractor: response uses resultSets/rows (camel) or ResultSets/Rows."""
    if not isinstance(result, dict):
        return []
    for k in ("resultSets", "ResultSets"):
        if k in result:
            sets = result[k]
            if set_index < len(sets):
                s = sets[set_index]
                return s.get("rows") or s.get("Rows") or []
    return []


def all_result_sets(result: dict) -> list[list[dict]]:
    if not isinstance(result, dict):
        return []
    sets = result.get("resultSets") or result.get("ResultSets") or []
    return [(s.get("rows") or s.get("Rows") or []) for s in sets]


def save_json(relpath: str, data) -> None:
    p = RAW / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).split(".")[0])
    except Exception:
        return None


def pull_clients(cp: ClientPortal) -> list[dict]:
    r = cp.list_active_clients()
    rows = first_rows(r)
    save_json("clients.json", rows)
    print(f"  clients        : {len(rows)} rows")
    return rows


def pull_proposals(cp: ClientPortal) -> list[dict]:
    r = cp.exec_sp("projectproposal", "GET_PROPOSALS_LIST",
                   {"UserID": 0, "FilterID": 0})
    rows = first_rows(r)
    # Filter to 5yr window by ProjectDate
    in_window = [p for p in rows if (d := parse_date(p.get("ProjectDate"))) and d >= FIVE_YR_CUTOFF]
    save_json("proposals.json", rows)               # full list (for audit)
    save_json("proposals_5yr.json", in_window)       # filtered
    print(f"  proposals      : {len(rows)} total, {len(in_window)} in 5-yr window")
    return in_window


def pull_work_progress(cp: ClientPortal) -> tuple[list[dict], list[dict]]:
    r = cp.exec_sp("projectproposal", "stp_Get_Peoposal_Work_Progress_List",
                   {"UserID": 0, "FilterID": 0})
    sets = all_result_sets(r)
    header = sets[0] if len(sets) > 0 else []
    detail = sets[1] if len(sets) > 1 else []
    save_json("work_progress_header.json", header)
    save_json("work_progress_detail.json", detail)
    print(f"  work progress  : {len(header)} headers, {len(detail)} detail rows")
    return header, detail


def pull_contracts(cp: ClientPortal) -> list[dict]:
    r = cp.exec_sp("contract", "GetAllContracts", {})
    rows = first_rows(r)
    save_json("contracts.json", rows)
    print(f"  contracts      : {len(rows)} rows")
    return rows


def pull_proposal_detail(cp: ClientPortal, proposals: list[dict]) -> None:
    """One call per proposal -> needs + schedule. Cache each proposal separately."""
    out_dir = RAW / "proposal_detail"
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(proposals)
    errors: list[dict] = []
    t0 = time.time()
    for i, p in enumerate(proposals, 1):
        pid = p.get("ProjectProposalID")
        if pid is None:
            continue
        f = out_dir / f"{pid}.json"
        if f.exists():
            continue  # resume-safe
        try:
            r = cp.exec_sp("projectproposal", "stp_Get_Project_Proposal", {"ProposalID": pid})
        except Exception as e:
            errors.append({"ProposalID": pid, "error": str(e)[:200]})
            continue
        sets = all_result_sets(r)
        f.write_text(json.dumps({
            "ProposalID": pid,
            "header": sets[0][0] if sets and sets[0] else None,
            "needs": sets[1] if len(sets) > 1 else [],
            "schedule": sets[2] if len(sets) > 2 else [],
        }, indent=2, default=str), encoding="utf-8")
        if i % 25 == 0 or i == total:
            rate = i / max(time.time() - t0, 0.01)
            eta = (total - i) / max(rate, 0.01)
            print(f"  proposal detail: {i}/{total}  ({rate:.1f}/s, ETA {eta:.0f}s)")
    if errors:
        save_json("proposal_detail_errors.json", errors)
        print(f"  errors: {len(errors)} (see raw/proposal_detail_errors.json)")


def main() -> int:
    cp = ClientPortal()
    print("Authenticating...")
    _ = cp.token()
    print(f"\nPulling core lists...")
    pull_clients(cp)
    proposals = pull_proposals(cp)
    pull_work_progress(cp)
    pull_contracts(cp)
    print(f"\nPulling proposal detail ({len(proposals)} proposals in 5-yr window)...")
    pull_proposal_detail(cp, proposals)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
