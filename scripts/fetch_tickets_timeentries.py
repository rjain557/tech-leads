"""Pull 12-month ticket + time-entry activity per client.

Uses `reports/stp_xml_Report_MonthlyActivityReport_TktTmEntry_Get` with
ClientID + FromDate + ToDate. That SP returns data as XML in
``outputParameters.XML_OUT`` — parsed via ClientPortal.xml_rows().

Each row (a <Report> element) is a ticket-work-period join with:
  TktCreateDate, TicketID, WorkPeriodDate, WorkPeriodTime, Employee, TktEntryNote

Output under tracking/kb/raw/ticket_timeentry/{DirID}.json (gitignored).
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
OUT = RAW / "ticket_timeentry"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    clients = json.loads((RAW / "clients.json").read_text(encoding="utf-8"))
    cp = ClientPortal()
    now = datetime.now()
    from_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    print(f"Pulling tickets+time-entries per client ({from_date} .. {to_date}) ...")
    total_reports = 0
    per_client: list[dict] = []
    errs: list[dict] = []
    t0 = time.time()
    for i, c in enumerate(clients, 1):
        cid = c["DirID"]
        cache = OUT / f"{cid}.json"
        if cache.exists():
            rows = json.loads(cache.read_text(encoding="utf-8"))
        else:
            try:
                r = cp.exec_sp(
                    "reports",
                    "stp_xml_Report_MonthlyActivityReport_TktTmEntry_Get",
                    {"ClientID": cid, "FromDate": from_date, "ToDate": to_date},
                )
            except Exception as e:
                errs.append({"DirID": cid, "Location_Name": c["Location_Name"], "error": str(e)[:200]})
                continue
            rows = ClientPortal.xml_rows(r, element="Report")
            cache.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        total_reports += len(rows)
        per_client.append({
            "DirID": cid, "LocationCode": c["LocationCode"],
            "Location_Name": c["Location_Name"], "row_count": len(rows),
        })
        if i % 10 == 0 or i == len(clients):
            rate = i / max(time.time() - t0, 0.01)
            print(f"  {i}/{len(clients)} clients  ({rate:.1f}/s)  total reports so far: {total_reports}")
    (RAW / "ticket_timeentry_summary.json").write_text(
        json.dumps({"from": from_date, "to": to_date, "per_client": per_client, "errors": errs}, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. {total_reports} ticket-work-period rows across {len(per_client)} clients.")
    if errs:
        print(f"  errors: {len(errs)}")
    # Clients with most activity
    per_client.sort(key=lambda x: -x["row_count"])
    print("\nTop clients by ticket+time-entry rows (12mo):")
    for p in per_client[:15]:
        if p["row_count"]:
            print(f"  {p['row_count']:5d}  {p['Location_Name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
