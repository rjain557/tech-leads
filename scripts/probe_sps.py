"""Probe SP catalog guides to discover parameters and result sets.

Writes one JSON per SP to tracking/kb/cache/sp-guides/{module}/{sp}.json for inspection.
Then prints a compact summary so we can pick the right SPs + params.
"""
from __future__ import annotations
import json
from pathlib import Path

from client_portal import ClientPortal, REPO

OUT = REPO / "tracking" / "kb" / "cache" / "sp-guides"
OUT.mkdir(parents=True, exist_ok=True)

# SPs to probe, grouped by intent. Names were picked from the Swagger enumeration.
CANDIDATES = {
    "clients": [
        # /api/clients/active is a simple REST, no SP. Probe clients module SPs too.
    ],
    "tickets": [
        "sp_Get_Ticket",
        "sp_Get_Ticket_Client",
        "stp_Get_Tickets_By_Status",
        "stp_Get_Tickets_Change_In_Status",
        "stp_xml_Ticket_Get_Ticket_Filter",
        "stp_xml_Ticket_Get_Ticket_Filter_WithCreator",
        "stp_xml_Tkt_PendingComplete_List_Get",
        "stp_xml_Tkt_Review_List",
        "stp_xml_Ticket_DSB_MyOpnTkt_List_Get_V2",
        "sp_CalendarHistory_List",
    ],
    "timeentry": [
        "sp_TicketEntry_List",
        "stp_Get_TicketEntry",
        "stp_xml_TicketDetail_TimeSheet_Detail_Get",
    ],
    "projectproposal": [
        "GET_PROPOSALS_LIST",
        "GET_PROPOSALS_LIST_VERSIONS",
        "stp_Get_Project_Proposal",
        "stp_Get_Peoposal_Work_Progress_List",
        "stp_xml_Prop_Org_Loc_Prop_List_Get",
        "stp_xml_Prop_Org_Loc_Prop_Header_Get",
        "stp_xml_Prop_Org_Loc_Prop_Detail_Sch_Get",
        "stp_xml_Prop_Org_Loc_Prop_Report_Get",
        "stp_xml_Prop_PropDSB_AllProp_List_Get",
    ],
    "contract": [
        "GET_CONTRACTS_LIST",
        "GetAllContracts",
        "stp_dt_Con_Org_Loc_Con_Contract_Get",
        "stp_dt_Con_Org_Loc_Prop_Con_Report_Get",
    ],
}


def main() -> int:
    cp = ClientPortal()
    summary: list[dict] = []
    for module, sps in CANDIDATES.items():
        for sp in sps:
            try:
                guide = cp.catalog_guide("client-portal", "dbo", sp)
            except Exception as e:
                summary.append({"module": module, "sp": sp, "error": str(e)})
                continue
            sub = OUT / module
            sub.mkdir(parents=True, exist_ok=True)
            (sub / f"{sp}.json").write_text(json.dumps(guide, indent=2), encoding="utf-8")
            # Pull a compact view
            params = guide.get("parameters") or guide.get("Parameters") or []
            if isinstance(params, dict):
                param_names = list(params.keys())
            else:
                param_names = [p.get("name") or p.get("Name") for p in params]
            summary.append({
                "module": module, "sp": sp,
                "params": param_names,
                "resultSets": len(guide.get("resultSets") or guide.get("ResultSets") or []),
            })
    (REPO / "tracking" / "kb" / "cache" / "sp-probe-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    for row in summary:
        if "error" in row:
            print(f"  ERR  {row['module']}/{row['sp']}: {row['error'][:80]}")
        else:
            print(f"  OK   {row['module']}/{row['sp']}  params={row['params']}  resultSets={row['resultSets']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
