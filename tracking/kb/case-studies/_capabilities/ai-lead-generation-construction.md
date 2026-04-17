# AI Lead Generation — Luxury Custom Home Builder

- **Capability:** AI · Multi-Source Scraping · Property-Data Enrichment · Lead Scoring
- **Applies to:** Any sales team whose leads come from slow-moving public data (permits, commission agendas, property records, HOA filings, recent sales)
- **Industry of reference build:** Construction — a boutique luxury custom home builder in Orange County coastal communities

## The problem

A small, high-touch custom home builder can't competitively scale a cold-outreach engine. The owner's weekly workflow before automation looked like this:

- Manually check active plan-check / permit portals across **10 Orange County jurisdictions** (5 different software platforms)
- Read Laguna Beach Design Review Board meeting notes once a month, click into plan-set PDFs, find the architect or owner in the title block
- Monitor **~60 HOA architectural-review committees** across Newport Coast, Dana Point, Laguna Beach, Irvine and more for submissions that precede city permits
- Watch for story-pole installations (a visible signal of a future build) across every Laguna Beach property and most Newport Beach HOAs
- Track Coastal Development Permit filings in the 5 coastal cities
- Skim Zillow / Redfin / Realtor for recent sales and identify the **buyer** agent (not the listing agent — that's the signal for a pending remodel)
- Monitor architect, designer, and real-estate-agent Instagram accounts for project announcements
- Skip-trace owner names into phone numbers via Spokeo

That's 15–20 hours a week of pattern-matching public data, before the builder has said a word to a prospect. It scales linearly with cities covered — it doesn't scale at all in real terms.

## What Technijian built

A multi-agent AI system that runs the entire above workflow end-to-end, adds **3–6 months of earlier detection** (most leads surface before a permit is filed, not after), and delivers a scored, tiered lead list per run.

### 7-layer signal architecture

```
MONTHS BEFORE PERMIT
 -6mo        -4mo         -3mo         -2mo         -1mo           0         +1mo

Just Sold  -> Geotech   -> Pre-App   -> ARC/Story  -> DRB/Plan  -> Permit  -> Instagram
(LLC/Trust    (Firm       (City        Poles          Commission   Filed     (in progress)
 buyers)      websites)   Staff)      (HOA             (City        (City
                                        agendas)       agenda)       portal)
```

Each layer is a discrete agent with its own portal-scraping logic, retry behavior, and output schema. The orchestrator dedups across layers and resolves addresses to APNs to stitch signals from different layers into a single lead record.

### 10 city + county permit agents

| Jurisdiction | Platform | Handled |
|---|---|---|
| Newport Beach | Tyler EnerGov | Login + 2FA handled in automation |
| Laguna Beach | Tyler EnerGov (SSO) | — |
| Costa Mesa | Tyler EnerGov | — |
| Laguna Niguel | Tyler EnerGov | — |
| San Juan Capistrano | eTRAKiT | — |
| Dana Point | eTRAKiT | — |
| San Clemente | eTRAKiT | — |
| Irvine | Custom ASP.NET | — |
| County of Orange | Maintstar | Covers Newport Coast, North Tustin, Villa Park, Emerald Bay, Coto de Caza |
| Huntington Beach | (city portal) | — |

### Design Review Board / DRC agents

Scrapes Granicus, Legistar, and CivicPlus agendas and staff reports; filters for the "recommendation for approval" language; extracts applicant name, property address, architect / agent, project scope, and the attached plan-set PDF link. Replaces the owner's monthly manual review of DRB agendas.

### HOA Architectural Review Committee tracking

60+ coastal HOAs registered as targets, organized by permit jurisdiction (City of Newport Beach vs. County of Orange vs. City of Dana Point). ARC submissions consistently lead city permits by 2–4 months — the system catches these first.

### Multi-source enrichment

For every candidate lead, the pipeline resolves:

- **APN** via county assessor + the city permit record
- **Assessed value** via OC Assessor API (`land`, `total`, `net`)
- **Laserfiche link** to the scanned permit documents (document count signals project maturity)
- **Owner name + mailing address** via ATTOM (by APN or address — dual-path fallback)
- **Phone + email** via BatchData skip-trace
- **Architect / designer** parsed from the title block of the plan-set PDF

The pipeline correctly handles **California Government Code §7928.205**, which prohibits online disclosure of property-owner names from every official Orange County source (Tax Collector, Assessor, Recorder, estream tax-bill PDFs). The automation knows not to waste cycles scraping those and goes straight to paid skip-trace — a rule that would take a new analyst weeks to discover.

### Scoring model

```
+5   new SFR (ground-up or demo + rebuild)
+5   vacant-lot build
+4   project SF > 3,000
+3   luxury amenities (pool, elevator, 3+ car garage, wine room, theater, BBQ terrace)
+3   applied within last 12 months
+2   premium location (oceanfront, ocean view, gated community, hilltop)
+2   major remodel + addition > 500 SF
+1   ADU as part of an estate scope (not ADU-only)
+1   status is "Under Review" or "In Process" (pre-builder selection window)
−2   status is "On Hold"
−3   applied before 2020 with no recent activity
```

Output is tiered: **Tier 1** (hot — immediate outreach), **Tier 2** (warm — watch-list), **Tier 3** (cold — monitor for status change).

### Tech stack

- **Node.js** orchestrator
- **Playwright + `playwright-extra` stealth plugin** for every portal — the permit sites are behind anti-bot and some require business-account 2FA
- **MCP servers**: Playwright MCP (agent-driven browser), Instagram-engagement MCP (architect / designer watch-list)
- **Data enrichment APIs**: OC Assessor, ATTOM (property), BatchData (skip-trace), Spokeo, eStreamOne (tax bill PDFs)
- **Output formats**: DOCX (briefing docs), XLSX (lead lists for CRM import), PDF (lead strategy datasheets)
- **Memory**: short-term JSON (in-run state), long-term Markdown (topic notes), run-index JSON (every run logged with counts)
- **Scheduled runs** via PowerShell orchestrator

## Evidence — one day of real runs

From the system's own run-index (one representative day, five runs):

| Run | Duration | Raw leads | Deduped | T1 | T2 | T3 | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| morning attempt 1 | 3s | 0 | 0 | 0 | 0 | 0 | failed |
| morning attempt 2 | 23m | 53 | 24 | 0 | 5 | 19 | completed |
| mid-morning | 46m | 220 | 77 | 0 | 6 | 71 | completed |
| midday | 48m | 222 | 77 | 0 | 6 | 71 | completed |
| **afternoon (final)** | **75m** | **216** | **194** | **24** | **36** | **134** | **completed** |

Afternoon run layer breakdown:

| Layer | Contribution |
|---|---|
| Permits across 10 jurisdictions | 173 raw |
| Design Review Boards | 48 raw → 26 valid (agenda boilerplate filtered out) |
| Coastal Development Permits | (empty this run) |
| Just-Sold | 17 valid (geo-filtered from cached data) |
| County Recorder | 104 |
| **Total** | 216 raw → 194 unique |

Enrichment yield on that same run:

- **ATTOM by APN:** 89 of 115 leads (77%)
- **ATTOM by address fallback:** 50 of 73 leads (68%)
- **BatchData skip-trace:** 132 of 188 leads (70% got a phone + email)

The first day produced **24 Tier-1 leads in a single 75-minute run** — each already enriched with assessed value, owner identity (via paid skip-trace), phone, email, and a direct Laserfiche link to the plan set.

## What this unlocks

- **3–6 months of earlier detection.** The builder is in the conversation before the prospect has picked a contractor.
- **No missed cities.** Manual monitoring of 10 portals across 5 software platforms doesn't happen reliably on any given week; the automation never skips a city.
- **Regulatory-aware.** The system knows the legal limits of public property data in California and doesn't waste runtime scraping sources that can't disclose owner names.
- **Compounding.** Every run's output is indexed; leads that appeared at Layer 1 (just-sold) three months ago are reconciled with Layer 5 (permit filed) today — same APN, now with a complete story.

## Outreach-ready summary

Most sales teams burn their Monday reading public-records portals. We built a multi-agent AI system that reads all of them continuously across 10 jurisdictions, stitches permit data to property records to HOA filings to just-sold signals, skip-traces the owners, and delivers a scored tiered lead list every morning. In the reference build for a luxury custom-home builder, the first production day surfaced 24 hot leads in a single 75-minute run — each with owner contact info, assessed value, and the architect's name off the plan set. The pipeline adds 3–6 months of earlier detection over manual monitoring because it watches the signals that *precede* the permit, not just the permit itself.
