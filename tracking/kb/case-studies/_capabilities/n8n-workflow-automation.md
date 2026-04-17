# n8n Workflow Automation

- **Capability:** Dev + Automation
- **Applies to:** Any services business with repeatable delivery steps

## What was built

A set of **5 production n8n workflows** that automate the end-to-end operational loop for an SEO / marketing services engagement:

- **Client Onboarding**
- **Content Pipeline**
- **Reporting Audit**
- **Paid Media Reporting**
- **Training Generator**

## How it works

- Workflows trigger from Microsoft Graph, email, or a slash command.
- Each workflow is parameterized per-client via a `client_manifest.json` in the   monorepo — new clients inherit the full automation stack on onboarding.
- Outputs flow into Teams/Planner for human review, not straight-to-client — the   automation handles the plumbing, humans own the judgment calls.

## Outcomes

- New-client onboarding: minutes, not days. Folder structure, agreements template,   initial audit, and workspace provisioning fire automatically.
- Reporting cadence: weekly + monthly reports generated on schedule without a PM   chasing data.
- Paid-media reporting: pulled from Google Ads API and delivered to the client's   inbox as a branded PDF.

## Outreach-ready summary

We don't sell 'an automation.' We sell a running ops backbone — 5 production n8n workflows handling onboarding, content pipeline, SEO reporting, paid-media reporting, and team training. It's the reason our SEO team can service 6+ clients with 4 people and still hit weekly cadence.
