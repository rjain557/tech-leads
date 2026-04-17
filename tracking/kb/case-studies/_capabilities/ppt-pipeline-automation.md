# Automated Status-Review Deck Generation

- **Capability:** Dev + Data-to-Presentation Automation
- **Applies to:** Any agency or services firm delivering recurring client reviews

## What was built

A Python pipeline (`weekly_pipeline.py`, 63 KB orchestrator + a 117 KB PPT generator) that ingests raw metric exports (.docx from SEMrush / HOTH / GSC / GA4 / OpenTable / PageSpeed) and emits a fully-branded, narrative-structured PPTX per client, per week — complete with speaker notes.

## How it works

- **Config-driven:** one `client_manifest.json` per client drives everything; a new   client slots into the pipeline with zero code changes.
- **Metric catalog:** a shared learnings doc codifies what "healthy" looks like per   metric (GSC CTR, GA4 bounce rate, PageSpeed, SEMrush rank distribution, OpenTable   no-show rate, etc.) so narrative generation is consistent across clients.
- **Outputs per run:** branded PPTX (6-section narrative), next-week ticket CSV   (auto-populated based on lowlights), structured metrics JSON for trend tracking.

## Outcomes

- A deck that took 4-6 hours manually now renders in under a minute.
- Speaker notes are drafted — the SEO lead reviews and edits rather than writing from   scratch.
- Next-week assignments flow out as a CSV, already routed to the right specialist   based on lowlight type (data-driven load balancing, not guesswork).

## Outreach-ready summary

Client status reviews shouldn't eat a day per client per week. We built a data-to-deck pipeline that handles everything from .docx metric intake to branded PowerPoint output with speaker notes — per client, per week, in under a minute each.
