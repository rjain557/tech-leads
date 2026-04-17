# AI-Avatar Video Production at Scale

- **Capability:** AI + Content Production
- **Applies to:** Any industry investing in educational or social video content

## What was built

A HeyGen-based video production pipeline with a documented workaround for the MCP server's known Pydantic validation bugs. Produces branded avatar-driven explainer videos on demand from a script + avatar ID.

## How it works

- Secrets sourced from a user-local `apikeys/` folder (never in repo).
- A monitor script polls the HeyGen job every 60 seconds, auto-downloads on `success`,   renames per the content calendar, and drops the file into the client's OneDrive   videos folder.
- The Antigravity skill (`heygen_video_generation.md`) captures every gotcha we've   hit (avatar vs. avatar-group IDs, voice-ID validation, how to fall back to   PowerShell `Invoke-RestMethod` when MCP fails) — documented once, every future   run is fast.

## Outcomes

- Branded explainer videos on a weekly cadence (e.g., the "2AM CyberBreach"   security-awareness series), without a videographer.
- Reusable across clients — swap avatar + script, keep the pipeline.

## Outreach-ready summary

We produce AI-avatar explainer videos on demand from a script — branded, on-brand, delivered weekly. Same economics as a YouTube short, same polish as a broadcast explainer.
