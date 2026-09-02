# ORACLE X Trust Boundaries

This document defines what each class of component may and may not do.

The goal is to prevent implementation drift, especially around AI-generated reasoning and broker execution.

## Core Rule

No LLM, AI agent, MCP tool call initiated by an agent, or agent-authored workflow may directly place, modify, or cancel an Alpaca order.

Broker execution is allowed only through deterministic execution services after deterministic risk and execution gates pass.

## AI Agent Boundary

AI agents are advisory components.

Agents may:

- Investigate possible opportunities.
- Draft trade theses.
- Challenge trade theses.
- Summarize evidence.
- Request deterministic calculations.
- Recommend strategy candidates.
- Explain calculations produced by deterministic services.
- Produce operator-facing summaries.
- Analyze completed trades.
- Suggest lessons learned.

Agents must not:

- Place Alpaca orders.
- Modify Alpaca orders.
- Cancel Alpaca orders.
- Approve trade risk.
- Override Risk Governor rejections.
- Override Execution Guard rejections.
- Generate authoritative numerical calculations.
- Mutate opportunity state directly.
- Bypass audit storage.
- Access broker secrets.
- Access Supabase service-role credentials from frontend or agent runtime contexts.

## Deterministic Application Boundary

Deterministic application services are trusted to perform bounded, testable operations.

They control:

- State-machine transitions
- Quantitative calculations
- Strategy normalization
- Stress calculations
- Risk evaluation
- Execution validation
- Broker submission
- Broker reconciliation
- Position monitoring
- Audit event writing
- Kill switch enforcement

These services must be tested and must avoid delegating control decisions to LLMs.

## Risk Governor Boundary

The Risk Governor is the only authority for risk approval.

It may:

- Approve risk.
- Reject risk.
- Request more data.
- Block trading due to system health.

It must evaluate deterministic inputs only. Agent rationale can be evidence, but cannot replace required calculations or constraints.

## Execution Guard Boundary

The Execution Guard is the final pre-submit validator.

It may:

- Permit deterministic execution service submission.
- Reject submission.
- Block stale, mismatched, duplicate, or unsafe orders.

It must run immediately before any Alpaca Trading API order request.

## Broker Boundary

### Alpaca Trading API

The Alpaca Trading API is the only runtime broker execution path.

Only the deterministic execution service may use it for:

- Submitting orders
- Modifying orders
- Canceling orders
- Reading order status
- Reading fills
- Reading positions
- Reconciling account state

Every execution-affecting call must be audited.

### Alpaca MCP

Alpaca MCP may be used only under a controlled policy.

Allowed use cases may include:

- Broker/account context
- Market or position inspection
- Auditable tool interactions
- Operational visibility

Forbidden use cases:

- Agent-driven order submission
- Agent-driven order modification
- Agent-driven order cancellation
- Any execution bypass around the Risk Governor or Execution Guard

### Alpaca CLI

The Alpaca CLI is for development, diagnostics, and manual operations.

It must not be wired into autonomous runtime execution.

## Database Boundary

PostgreSQL/Supabase is the durable source of truth.

The database must preserve:

- State transitions
- Agent decisions
- Inference traces
- Quantitative calculations
- Risk evaluations
- Execution validations
- Broker requests and responses
- Orders
- Fills
- Positions
- Autopsies
- Memory records

Where practical, audit records should be append-only.

## Frontend Boundary

The War Room frontend is an operator interface.

It may:

- Display opportunities.
- Display state and risk status.
- Display audit history.
- Display orders, fills, and positions.
- Request allowed backend actions.

It must not:

- Store broker secrets.
- Call Alpaca directly.
- Hold Supabase service-role credentials.
- Bypass backend authorization.
- Mutate trading state without backend validation.

## Inference Boundary

Featherless and any future inference provider produce advisory outputs.

Inference may support:

- Opportunity interpretation
- Thesis generation
- Thesis challenge
- Summarization
- Autopsy narrative
- Memory extraction

Inference must not:

- Authorize execution.
- Replace deterministic calculations.
- Override failed risk checks.
- Override failed execution checks.

## Secret Boundary

Secrets must remain server-side.

Protected secrets include:

- Alpaca API credentials
- Featherless API credentials
- Supabase service-role credentials
- Broker credentials
- Market-data credentials
- MCP credentials

Logs, audit events, inference traces, and frontend payloads must redact secrets and sensitive headers.

## Live Trading Boundary

Paper trading is the default target.

Live trading must require:

- Explicit environment configuration
- Operator awareness
- Protective limits
- Kill switch
- Broker/account validation
- Strong auditability

No implementation should accidentally enable live trading by default.
