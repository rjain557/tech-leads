# AI Agent Architecture for SEO Delivery

- **Capability:** AI + Automation
- **Applies to:** Any industry running a content-heavy SEO program

## What was built

A multi-agent SEO delivery system built on Google Antigravity. Each specialist capability is encoded as a discrete agent Skill, allowing a small human team (4 FTE) to operate as if it were a 10-15 person agency.

**13 specialized skills** live in the agent runtime, including:

- Presentation Architect
- Content Refinery
- Education Architect
- Local Prime
- Negative Seo
- Paid Media Manager
- Planner
- Pmax Campaign Manager
- Shopify Liquid
- Social Distributor
- Sst Stape
- Technijian Voice
- Wordpress Architect

## How it works in practice

- **MCP servers** wire the agents to live tools: SEMrush (audit + rank tracking),   Microsoft Graph (Planner/Teams), Playwright (site verification), n8n (workflow   automation), HeyGen (avatar-driven video).
- **Skill composition:** the Planner skill decomposes a weekly status review into   tasks, routes each to the right specialist Skill (content refinery, local prime,   WordPress architect, paid-media manager, etc.), and assembles the result.
- **Brand consistency:** a single `technijian-voice` skill enforces tone across every   client-facing artifact the agents generate.

## Outcomes

- Weekly PPTX status reviews generated automatically per client,   with speaker notes and structured metrics JSON. ~8 clients produced in minutes   instead of days.
- Content pipeline, paid-media reporting, and client onboarding each templatized   as an n8n workflow — new clients onboard in hours.
- HeyGen workflow produces branded explainer videos from a script + avatar ID,   with automated polling and delivery to the client drive.

## Outreach-ready summary

We operate a multi-agent AI system that automates the busywork of SEO delivery — status reviews, content routing, site verification, ranking analysis, even branded video — so the human specialists focus on strategy and client relationships. It's production, not experimental.
