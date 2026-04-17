# Flagship AI Development — Enterprise Multi-Tenant AI SaaS Platform

- **Capability:** AI Development · Full-Stack · Platform Engineering
- **Status:** Alpha (live); GA launch within 4 weeks
- **Scale:** ~29,800 files tracked in the monorepo; single-PR pipeline
- **Applies to:** Any enterprise customer considering a custom AI product instead of stitching SaaS point tools together

## What Technijian built

A production-grade multi-tenant AI SaaS platform — not a prototype. It runs as Technijian's own upcoming product launch, which doubles as the reference implementation for the custom AI work we offer to enterprise clients.

**Core product surface** (primary navigation, role-aware):

- **Chat** — multi-LLM conversational UI with threaded history, context panels, and per-thread model / assistant selection
- **Council** — multi-LLM deliberation: the same prompt runs across several models concurrently, results compared, transcripts retained
- **Projects** — long-running AI workstreams with per-project memory, assistants, files, and connectors
- **Assistants** — custom system-prompted agents, CRUD-managed, shareable across a tenant
- **Files** — secure tenant-scoped file store wired into chat context
- **Connectors** — outbound integrations (n8n, Microsoft Graph, and more) available inside chats
- **Workflows** — visual tool catalog + workflow runs, including an in-browser workflow builder with undo history
- **Help** — in-product docs and education surface

**Admin surface** (role-gated):

Tenants · Directory · Connectors · n8n Servers · Memory · LLM Models · LLM Providers · LLM Logs · Council Settings · Revenue / Billing · Usage & Health · Audit.

**LLM breadth:** OpenAI, Anthropic, Google Vertex, Azure OpenAI, Cohere, Mistral, Groq, Z.ai — routed through a provider abstraction and governed by a per-tenant model pool with assignment rules.

**Compliance from day one:**

- HIPAA audit trail on every privileged operation (database-level inserts from every admin stored procedure)
- Tenant isolation enforced at the database layer via `SESSION_CONTEXT` — every SP derives `TenantId` from the session, not the caller
- GDPR data-subject rights: self-service export, erasure with a 30-day grace window, cancel-erasure, status query — controller + SP + audit log all wired
- Rate limiting at both user (100/min) and tenant (1000/min) scope
- Redis-backed security monitoring: failed-login lockout, cross-tenant anomaly detection, identifier redaction in logs
- Azure AD (MSAL) + JWT with proper refresh-token rotation and race-condition-safe issuance

**Stack:**

- Frontend: React 18 + TypeScript + Vite + TailwindCSS + Zustand + React Query
- Backend: ASP.NET Core 8 + Dapper + SQL Server
- **Database rule: stored procedures only** — no ORM-generated SQL, no ad-hoc queries. Every data access goes through a named SP with an explicit audit contract.
- Auth: Azure AD / Entra ID via MSAL; JWT with rotating refresh tokens
- Design source of truth: Figma (design-first workflow; UI contract versioned in the repo)

## How Technijian built it — the GSD autonomous development pipeline

The interesting part for a buyer isn't just *that* we built this. It's *how fast, and at what quality*, because the same pipeline is what we would run on their project.

Technijian built and is running **GSD (Goal-Spec-Done)** — a 14-agent autonomous development system that drives a .NET + React + SQL Server project from "here's a project description" through architecture, Figma validation, contract freeze, code review, remediation, quality gates, and alpha deployment.

**The 14 agents, in pipeline order:**

Phase A–E (SDLC, human-in-the-loop):
- **RequirementsAgent** — drafts an intake pack from a project description
- **ArchitectureAgent** — emits diagrams, a draft OpenAPI spec, and a threat model
- **FigmaIntegrationAgent** — validates the full 12-of-12 Figma Make deliverables
- **PhaseReconcileAgent** — reconciles requirements after prototype feedback
- **BlueprintFreezeAgent** — freezes the implementation blueprint
- **ContractFreezeAgent** — locks SCG1 contracts and issues a validation report

Phase F–G (pipeline, runs unattended):
- **Orchestrator** — routes work, decides retry vs. escalate vs. halt; logs a Decision record for every routing choice
- **BlueprintAnalysisAgent** — reads specs, detects drift between design and code
- **CodeReviewAgent** — runs review (and chains three LLMs in parallel — Claude, Codex, Gemini)
- **RemediationAgent** — auto-fixes identified issues
- **QualityGateAgent** — runs tests, `npm audit`, `dotnet` vulnerability checks
- **E2EValidationAgent** — tests API contracts, stored procedures, mock-data policies, and auth
- **DeployAgent** — deploys with automated rollback
- **PostDeployValidationAgent** — validates the live alpha environment (SPA cache, dependency injection, 500-error scan)

**What makes it work in production:**

- **Vault-backed memory.** Every agent's system prompt, every architecture contract, every orchestrator decision lives in an Obsidian vault indexed by the agents themselves. Humans edit prompts in the vault, not in code — the runtime picks up the change on next run.
- **Dual-auth routing to hit $0 marginal cost.** Primary path uses CLI OAuth subscriptions (Claude Code, OpenAI Codex, Gemini). API keys are a *backup* path that only triggers when a subscription hits a rate limit. Result: steady-state cost stays at the fixed subscription price.
- **Code-intelligence augmentation stack.** Graphify for knowledge graphs, GitNexus for impact analysis before any symbol edit, Context7 for up-to-date library docs, Semgrep + OWASP for security scanning, Playwright for browser validation, GitHub MCP for repo operations, Shannon for code-review orchestration.
- **Impact-analysis gates.** No agent renames a symbol without first running a call-graph impact analysis and halting on HIGH / CRITICAL risk for human review.
- **Three-model code review.** Each review cycle runs Claude, Codex, and Gemini in parallel against the same diff. Findings are merged; the RemediationAgent picks up the union set.

## Outcomes — the ChatAI build itself

Evidence from the ChatAI v8 handoff, not talking points:

- **450 requirements reviewed** across the SDLC phases
- **3 rounds of 3-model code review** (Claude + Codex + Gemini per round) plus auto-remediation between rounds
- **521 issues identified → 113 remaining after round 1 → 0 critical at verification**, with all high / medium / low addressed by round 3
- **Alpha environment live** at `alpha-chatai.technijian.com` (SPA) and `alpha-chatai-api.technijian.com` (API); health endpoint green
- **Launch target: within the next 4 weeks**

## What this unlocks for an enterprise client

- Custom AI products — not an AI skin on top of a SaaS tool — delivered with the same pipeline that shipped this platform
- Compliance isn't a post-hoc patch: HIPAA audit, tenant isolation, GDPR rights, and rate limiting are part of the generator, not bolted on later
- Multi-LLM vendor independence from day one — no lock-in to a single model provider
- Design-first discipline: the Figma spec is the contract, not a suggestion

## Outreach-ready summary

Technijian is launching its own multi-tenant AI SaaS in the next four weeks — built end-to-end with GSD, the 14-agent autonomous development pipeline we also operate. The same pipeline (requirements → architecture → Figma validation → blueprint freeze → three-model code review → remediation → quality gates → deploy → post-deploy validation) is what we would run on your AI build. You'd get a production-grade platform — multi-LLM, multi-tenant, HIPAA-compliant, audit-logged, rate-limited — with the code review and drift detection running inside the pipeline, not as an afterthought. Ask to see the alpha.
