# Exact Codex Handoff Prompt

You are taking over implementation of **ORACLE X**, an autonomous AI trading intelligence committee for the Alpaca AI Trading Agents Hackathon.

This repository contains the authoritative engineering contract.

## FIRST: DO NOT CODE BLINDLY

Before writing implementation code:

1. Read `AGENTS.md` completely.
2. Read every document in `docs/`.
3. Inspect the entire repository and identify what already exists.
4. Do not discard existing work without proving it is obsolete.
5. Produce a short implementation audit:
   - what exists;
   - what is missing;
   - what conflicts with the docs;
   - what should be built first.

Do not ask for permission for routine implementation decisions that are already specified by the docs.

## Authoritative architecture

- Featherless = LLM inference layer.
- ATHENA = opportunity intelligence.
- HADES = adversarial critic.
- HERMES = options strategy structurer.
- MORPHEUS = stress tester.
- Alpaca MCP = agent-facing research/tool access.
- Alpaca Trading API = controlled execution.
- Alpaca CLI = operational automation/diagnostics/reconciliation.
- Risk Governor = deterministic hard safety boundary.
- Execution Guard = final mechanical gate.
- PostgreSQL/Supabase = source of truth.
- Paper trading = required during development/demo.

## Implementation order

Execute in this order unless repository inspection reveals an existing equivalent:

### Phase 1 — Foundation
- establish Python backend;
- establish frontend shell;
- establish configuration/environment validation;
- establish structured logging;
- establish database connection;
- establish migration workflow.

### Phase 2 — Domain contracts
Implement Pydantic/domain models for:
- opportunities;
- agent decisions;
- option strategies/legs;
- trades;
- risk evaluations;
- orders;
- execution events;
- positions;
- lifecycle events.

### Phase 3 — State machine
Implement the canonical state machine in `docs/STATE-MACHINE.md`.

Requirements:
- explicit allowed transitions;
- invalid transition rejection;
- evidence requirement;
- event emission;
- tests.

### Phase 4 — Featherless adapter
Implement a provider abstraction and Featherless adapter.

Requirements:
- OpenAI-compatible endpoint;
- server-side API key;
- structured JSON output;
- timeout/error handling;
- inference trace persistence;
- provider/model/prompt/version metadata;
- no execution authority.

### Phase 5 — Agent runtime
Implement Athena, Hades, Hermes and Morpheus as typed agent services.

Start with deterministic/mock evidence fixtures so tests do not depend on live APIs.

Then connect live Featherless inference.

### Phase 6 — Alpaca MCP integration
Implement an MCP client/tool layer with explicit per-agent allowlists.

Agents must never receive execution tools.

Record MCP tool calls in `mcp_tool_calls`.

### Phase 7 — Quantitative services
Implement deterministic calculation modules.

Do not ask the LLM to calculate execution-critical values.

All important calculations require tests.

### Phase 8 — Risk Governor
Implement deterministic policy evaluation.

Every gate returns structured reason codes and measured values.

Write unit tests for pass/boundary/fail cases.

### Phase 9 — Execution Guard
Implement final validation.

It must verify:
- approved state;
- valid strategy;
- successful risk evaluation;
- paper mode;
- fresh evidence;
- no position mismatch;
- no duplicate order;
- system ACTIVE.

### Phase 10 — Alpaca execution adapter
Only this adapter can submit orders.

Implement:
- client_order_id;
- order persistence;
- submission;
- broker confirmation;
- reconciliation;
- safe retry behavior.

Unknown order status must never be blindly retried.

### Phase 11 — Event/audit/replay
Persist all major lifecycle events.

Implement a decision replay query/service that can reconstruct:
- evidence;
- agent decisions;
- critique;
- strategy;
- stress tests;
- risk result;
- execution;
- outcome.

### Phase 12 — Learning
Implement trade autopsy and memory persistence.

Learning must not silently modify hard risk rules.

### Phase 13 — War Room
Build a compelling frontend showing:
- live committee activity;
- evidence;
- disagreement;
- strategy;
- stress results;
- Governor verdict;
- execution;
- P&L;
- audit trail;
- replay/autopsy.

## Required tests

At minimum:

`test_athena.py`
`test_hades.py`
`test_hermes.py`
`test_morpheus.py`
`test_risk_governor.py`
`test_state_machine.py`
`test_execution_guard.py`
`test_alpaca_adapter.py`
`test_idempotency.py`
`test_reconciliation.py`

The following must be demonstrably true:

1. Excessive risk is rejected.
2. Low reward/risk is rejected.
3. Invalid lifecycle transitions are rejected.
4. Missing approval is rejected.
5. Live trading mode is rejected in hackathon mode.
6. Duplicate client order IDs cannot submit twice.
7. Unknown broker submission is reconciled before retry.
8. An LLM output cannot bypass the Governor.
9. MCP execution tools are unavailable to all four agents.
10. Dependency failure fails closed.

## Coding rules

- Prefer typed Python and Pydantic.
- Keep domain logic independent from vendor SDKs.
- Wrap Featherless and Alpaca behind adapters.
- Do not hard-code secrets.
- Do not put business logic in frontend components.
- Keep functions small and testable.
- Use dependency injection where useful.
- Add correlation IDs to workflows/events.
- Use migrations, not ad-hoc production schema changes.
- Preserve audit data.
- Do not delete safety checks to make a demo work.

## Git workflow

Make small commits after meaningful milestones.

Suggested sequence:
1. `chore: establish oracle x foundation`
2. `feat: add domain contracts`
3. `feat: implement lifecycle state machine`
4. `feat: add featherless inference adapter`
5. `feat: implement committee agents`
6. `feat: add alpaca mcp integration`
7. `feat: implement deterministic risk governor`
8. `feat: add execution guard and idempotency`
9. `feat: add alpaca execution adapter`
10. `feat: add replay and audit trail`
11. `feat: build oracle x war room`

## Final operating rule

When there is tension between making the demo flashy and preserving correctness, preserve correctness.

The goal is not to build a chatbot that can trade.

The goal is to build a defensible AI trading committee where:
**models reason, deterministic software governs, Alpaca executes, and every decision can be replayed.**
