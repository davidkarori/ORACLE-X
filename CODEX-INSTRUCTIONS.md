# Codex Instructions For ORACLE X

These instructions apply to every Codex session working in this repository.

ORACLE X is a trading intelligence and execution-control system. Treat it as safety-sensitive software. Do not assume agent reasoning is sufficient for trading decisions or broker execution.

## Required Read Order

Before implementation work, read:

1. `AGENTS.md`
2. `README.md`
3. `CODEX-INSTRUCTIONS.md`
4. Files under `docs/`
5. Supabase migrations
6. `.env.example`
7. `.gitignore`

If any required file is missing, report that before proceeding.

## Prime Safety Rule

No LLM, AI agent, MCP tool call initiated by an agent, or agent-authored workflow may directly place, modify, or cancel an Alpaca order.

Order execution may happen only through deterministic application code after:

1. Valid opportunity lifecycle state.
2. Deterministic quantitative calculations.
3. Risk Governor approval.
4. Execution Guard validation.
5. Idempotent execution service submission through the Alpaca Trading API.

If a requested change weakens this rule, stop and ask for explicit approval.

## Implementation Discipline

When asked to implement:

- Inspect the existing repository before editing.
- Preserve the architecture in `AGENTS.md`.
- Keep changes scoped.
- Prefer explicit types and schemas for trading data.
- Prefer deterministic services for calculations and control decisions.
- Persist audit records for important decisions and external interactions.
- Add tests for state, risk, execution, broker, and schema behavior.
- Do not redesign the stack without explicit approval.
- Do not introduce direct broker execution paths from agent code.
- Do not put secrets in source files.

## Agent Authority

Agents may:

- Investigate opportunities.
- Draft theses.
- Challenge theses.
- Summarize market evidence.
- Request deterministic calculations.
- Recommend strategies.
- Explain deterministic outputs.
- Record reasoning for audit.
- Analyze completed trades.

Agents must not:

- Approve risk.
- Submit, modify, or cancel orders.
- Override Risk Governor decisions.
- Override Execution Guard decisions.
- Invent authoritative quantitative values.
- Mutate lifecycle state directly.
- Bypass audit logging.

## Deterministic Services

The following must be deterministic application code:

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
- Risk Governor decisions
- Execution Guard decisions
- Broker submission
- Position reconciliation

LLMs can narrate or interpret results, but they are not the source of truth.

## State Machine Requirements

Opportunity state must follow an explicit lifecycle.

Expected happy path:

```text
DETECTED
-> INVESTIGATING
-> THESIS_CREATED
-> THESIS_CHALLENGED
-> STRATEGY_SELECTED
-> STRESS_TESTED
-> RISK_EVALUATED
-> APPROVED
-> EXECUTION_READY
-> SUBMITTED
-> FILLED
-> POSITION_OPEN
-> POSITION_MONITORING
-> EXIT_SIGNAL
-> EXIT_EXECUTION
-> POSITION_CLOSED
-> AUTOPSY
-> LEARNED
```

State transitions must be:

- Enforced in application code.
- Persisted to the database.
- Auditable.
- Idempotent where needed.
- Rejected when invalid.

Expected failure or rejection states include:

- `REJECTED_BY_HADES`
- `REJECTED_BY_RISK`
- `REJECTED_BY_EXECUTION_GUARD`
- `DATA_STALE`
- `BROKER_UNAVAILABLE`
- `KILL_SWITCH_ACTIVE`
- `EXECUTION_FAILED`
- `CANCELLED`
- `EXPIRED`

## Risk Governor Requirements

The Risk Governor must be deterministic and fail closed.

It should evaluate:

- System hard limits
- Per-trade max loss
- Daily loss
- Portfolio exposure
- Position sizing
- Concentration
- Liquidity
- Options max loss
- Data freshness
- Broker health
- Account status
- Existing positions
- Pending orders
- Kill switch status

Risk evaluations must be durable, machine-readable, and linked to the opportunity.

## Execution Guard Requirements

The Execution Guard runs immediately before broker submission.

It must verify:

- Opportunity state is `EXECUTION_READY`.
- Risk approval is present, valid, and unexpired.
- Kill switch is inactive.
- Broker/account status is healthy.
- Market/session conditions permit execution.
- Market data is fresh.
- Final order matches the approved strategy.
- All legs are valid.
- Buying power and max loss still pass.
- No duplicate active order exists.
- Idempotency key is valid.
- Execution validation has been audited.

Any failure blocks submission.

## Alpaca Usage

Use Alpaca integrations according to this split:

- Alpaca MCP: controlled, auditable context/tool access only.
- Alpaca Trading API: deterministic runtime execution path only.
- Alpaca CLI: development, diagnostics, and manual operations only.

Do not allow autonomous agents to use Alpaca MCP or Alpaca CLI as an execution path.

## Featherless Usage

Featherless is the intended first-class inference provider.

Implementation should include:

- Provider interface
- Featherless adapter
- Server-side API key configuration
- Model selection policy
- Request timeouts
- Retry policy
- Structured request and response handling
- Trace persistence
- Error classification
- Secret redaction
- Fail-closed behavior

Inference failure must never authorize execution.

## Database Expectations

The database should preserve durable records for:

- Opportunities
- Lifecycle transitions
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

Prefer constraints and indexes that enforce correctness rather than relying only on application convention.

## Testing Expectations

For any meaningful implementation, add or update relevant tests.

Required test categories:

- Unit tests
- State-machine tests
- Quantitative service tests
- Options strategy tests
- Risk Governor tests
- Execution Guard tests
- Featherless adapter tests
- Alpaca adapter tests
- MCP boundary tests
- Database migration tests
- Audit/replay tests
- Paper-trading smoke tests

Include adversarial tests proving agents cannot bypass deterministic execution controls.

## Secrets And Security

Never commit secrets.

Keep these server-side:

- Alpaca credentials
- Featherless credentials
- Supabase service credentials
- Broker credentials
- Market-data credentials
- MCP credentials

Frontend code must not receive broker secrets or unrestricted service-role credentials.

Paper trading should be the default. Live trading must require explicit configuration and protective controls.

## Build Sequence

Recommended implementation order:

1. Foundation docs and environment contract.
2. Supabase schema.
3. State machine.
4. Deterministic quantitative services.
5. Featherless adapter.
6. Agent runtime.
7. Risk Governor.
8. Execution Guard.
9. Alpaca paper-trading adapter.
10. Reconciliation and monitoring.
11. War Room frontend.
12. Audit replay.
13. Autopsy and memory.
14. End-to-end and adversarial testing.
15. Deployment.

## Stop Conditions

Stop and ask before:

- Weakening an agent or execution boundary.
- Enabling live trading.
- Adding a direct order path from agent code.
- Removing audit logging from trading decisions.
- Storing secrets in files.
- Replacing deterministic calculations with LLM calculations.
- Changing the lifecycle without updating the architecture docs.
