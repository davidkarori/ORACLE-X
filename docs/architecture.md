# ORACLE X Architecture

ORACLE X is a trading intelligence and execution-control system. It combines AI-assisted research with deterministic software controls so that reasoning, risk evaluation, execution, audit, and learning remain separate and traceable.

The central architectural principle is simple:

AI agents produce advisory intelligence. Deterministic services control calculations, risk approval, execution validation, broker submission, state transitions, and audit integrity.

## System Components

### Agent Layer

The agent layer contains bounded AI roles:

- **Athena** discovers opportunities, interprets market evidence, and drafts theses.
- **Hades** challenges theses, identifies risks, and records dissent.
- **Hermes** coordinates messages, tool calls, and system-facing summaries.
- **Morpheus** performs autopsy, replay analysis, and memory extraction after trades close.

Agents may recommend. They may not execute.

### Inference Layer

Featherless is the intended first-class inference provider.

The inference layer should expose a provider interface so agent code does not depend directly on one provider's HTTP contract. Every inference request and response should be traceable, linked to the relevant opportunity or position, and redacted before durable storage when necessary.

Inference failures must fail closed. A failed or unavailable model cannot authorize risk approval, execution readiness, or order submission.

### Quantitative Services

Quantitative services are deterministic application services. They calculate the authoritative values used by the rest of the system.

These services own:

- Indicators
- Returns
- Realized volatility
- Implied volatility
- Greeks
- Spreads
- Reward/risk
- Exposure
- P&L
- Position sizing
- Stress calculations
- Liquidity checks
- Max loss

Agents may request and explain calculations, but the values must be produced by deterministic code.

### Risk Governor

The Risk Governor is the deterministic authority for risk approval.

It evaluates whether a strategy is permitted under system limits, portfolio exposure, position sizing, liquidity, max loss, daily loss, broker health, data freshness, current positions, pending orders, and kill-switch state.

The Risk Governor emits durable decisions:

- `APPROVED`
- `REJECTED`
- `NEEDS_MORE_DATA`
- `SYSTEM_BLOCKED`

Risk approvals must expire and must be rechecked before execution.

### Execution Guard

The Execution Guard runs immediately before broker submission.

It verifies that the opportunity is in the correct state, the risk approval remains valid, the system is healthy, market data is fresh, the final order matches the approved strategy, all legs are valid, no duplicate order exists, and the action is idempotent.

If any validation fails, no broker call is allowed.

### Execution Service

The execution service is the only runtime component allowed to submit, modify, or cancel Alpaca orders.

It may call the Alpaca Trading API only after Risk Governor approval and Execution Guard validation. It must record request metadata, response metadata, idempotency keys, order identifiers, fills, and errors.

### Alpaca Integrations

ORACLE X separates Alpaca usage into three categories:

- **Alpaca MCP**: controlled and auditable context/tool interactions.
- **Alpaca Trading API**: deterministic execution path for runtime broker orders.
- **Alpaca CLI**: development, diagnostics, and manual operations.

Agents must not use any Alpaca integration as a direct execution path.

### Database

PostgreSQL/Supabase is the durable source of truth.

The database should preserve:

- Opportunities
- State transitions
- Agent decisions
- Inference traces
- MCP calls
- Quantitative calculations
- Strategies
- Trade legs
- Options contracts
- Risk evaluations
- Execution validations
- Orders
- Fills
- Positions
- Position snapshots
- Reconciliation events
- Autopsies
- Memory records
- System state
- Kill switch events

Audit records should be append-only wherever practical.

### War Room Frontend

The War Room is the operator-facing frontend.

It should show:

- Active opportunities
- Lifecycle state
- Agent rationale
- Hades challenges
- Deterministic calculations
- Risk Governor decisions
- Execution Guard results
- Orders and fills
- Open positions
- Alerts and system health
- Replay and autopsy views

The frontend must not receive broker secrets or unrestricted service credentials.

### Audit And Replay

Every important decision and external interaction must be durable and reconstructable.

ORACLE X should be able to answer:

"Why did this trade happen?"

The answer must be reconstructable from stored market evidence, agent decisions, inference traces, MCP calls, deterministic calculations, risk evaluations, execution validations, broker orders, fills, position lifecycle events, exits, autopsies, and lessons learned.

## High-Level Flow

```text
Market evidence
-> Athena investigation
-> Hades challenge
-> Deterministic strategy calculations
-> Stress testing
-> Risk Governor
-> Execution Guard
-> Execution service
-> Alpaca Trading API
-> Fill and position monitoring
-> Exit handling
-> Autopsy
-> Memory
```

At no point does an agent receive direct broker execution authority.

## Failure Philosophy

ORACLE X must fail closed.

If data is stale, inference fails, broker health is uncertain, audit logging fails, risk approval expires, state is invalid, or the kill switch is active, execution must stop.
