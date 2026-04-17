# My Continuity — Outreach template

**Frame:** Company hiring BCDR / Backup / Veeam admin — often post-ransomware event, pre-cyber-insurance renewal, or after a failed restore test. Pitch: Veeam-powered 3-2-1-1-0 immutable backups, cross-cloud DR, orchestrated failover, quarterly restore drills with audit evidence.

## Subject variants

1. Re: your {{role}} posting
2. About the {{role}} role at {{company}}
3. Backup posture question — {{role}} JD

## Touch 1 — Day 0

> Hi {{contact_first_name}},
>
> Saw the {{role}} posting. The "{{jd_quote}}" line tells me {{company}} is either firming up backup posture for a cyber-insurance renewal or cleaning up after a close call.
>
> Either way — we run Veeam-managed 3-2-1-1-0 immutable backups with quarterly restore drills and audit evidence on tap. Most shops discover their backups don't restore only after they need them; the point of the managed layer is that we find out on a Tuesday, not during an incident.
>
> Worth 15 min to compare against what the new hire would inherit?
>
> {{signature}}

## Touch 2 — Day 4

> {{contact_first_name}} — the one test that separates real BCDR from paper BCDR: pull the primary datacenter at 8am on a Wednesday and see if anyone notices. Most orgs discover their runbooks silently assume the architect is awake and reachable. Ours assume the architect is out of reach.
>
> Short call?
>
> {{signature}}

## Touch 3 — Day 10

> Did the {{role}} close? If the backups-never-tested problem is still open, I can send the restore-drill checklist we use — no call needed.
>
> {{signature}}

## Service-specific DO

- If there's a public ransomware event at the company or vertical in the last 90 days, reference it carefully (news link, not speculation)
- Lead with restore-drill evidence — it's the audit question that trips up in-house BCDR the most
- Use the 3-2-1-1-0 phrase verbatim — it signals Veeam literacy

## Service-specific DON'T

- Do NOT fear-sell ("if you get hit…"). Backup buyers have heard every scare story
- Don't pitch immutability without explaining why — the "why" (ransomware recovery) is what earns the reply
