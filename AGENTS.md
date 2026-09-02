# ORACLE X Agent Governance

This document is the governing contract for all human and AI-assisted implementation work in ORACLE X.

ORACLE X is a trading intelligence and execution-control system. Its architecture must preserve a strict boundary between AI-generated reasoning and deterministic software controls. Agents may help discover, explain, challenge, and summarize opportunities, but they must never directly execute trades or bypass deterministic risk and execution gates.

## Prime Directive

No LLM, AI agent, MCP tool call initiated by an agent, or agent-authored workflow may directly place, modify, or cancel an Alpaca order.

Alpaca order execution is permitted only through deterministic application code after:

1. The opportunity reaches the required lifecycle state.
2. Deterministic quantitative services calculate all required metrics.
3. The deterministic Risk Governor approves the trade.
4. The deterministic Execution Guard validates the final order immediately before submission.
5. The execution service submits the order through the Alpaca Trading API using an idempotent request.

If any required validation, dependency, broker check, or audit write fails, the system must fail closed.

## Agent Roles

### Athena

Athena is responsible for opportunity discovery, market interpretation, thesis drafting, and evidence synthesis.

Athena may:

- Identify possible opportunities.
- Summarize market evidence.
- Propose a trade thesis.
- Request deterministic calculations from quantitative services.
- Attach reasoning and evidence to an opportunity record.

Athena must not:

- Approve trades.
- Calculate authoritative risk values.
- Submit, modify, or cancel orders.
- Override rejected opportunities.
- Mutate lifecycle state outside the orchestrator.

### Hades

Hades is responsible for adversarial review, thesis challenge, failure-mode discovery, and risk critique.

Hades may:

- Challenge Athena's thesis.
- Identify missing evidence.
- Propose reasons to reject or delay a trade.
- Request deterministic stress tests.
- Record critique and dissent.

Hades must not:

- Approve trades.
- Submit, modify, or cancel orders.
- Replace deterministic risk controls with qualitative judgment.
- Override the Risk Governor.

### Hermes

Hermes is responsible for coordination, messaging, tool mediation, and traceable communication between components.

Hermes may:

- Route requests between agents and deterministic services.
- Record MCP calls and external tool interactions.
- Summarize system status for the War Room.
- Coordinate notifications and operator-facing messages.

Hermes must not:

- Use MCP access as a trade execution bypass.
- Submit, modify, or cancel orders.
- Hide failed tool calls or failed validations.
- Convert advisory agent output into execution authority.

### Morpheus

Morpheus is responsible for post-trade autopsy, replay, learning, and memory.

Morpheus may:

- Analyze completed trade outcomes.
- Compare thesis expectations against actual results.
- Extract lessons learned.
- Store memory records for future retrieval.
- Support replay and operator review.

Morpheus must not:

- Alter historical audit records.
- Rewrite trade rationale after execution.
- Approve future trades.
- Use memory to bypass deterministic controls.

## Deterministic Services

The following capabilities must be implemented as deterministic application code, not as LLM-generated calculations:

- Indicators
- Returns
- Realized volatility
- Implied volatility
- Greeks
- Spreads
- Reward/risk
- Portfolio exposure
- Position sizing
- Stress calculations
- P&L
- Max loss
- Liquidity checks
- Concentration checks
- Broker and data-health checks
- Position reconciliation

LLMs may explain deterministic results, but the database must preserve which deterministic service produced each authoritative value.

## Risk Governor

The Risk Governor is a deterministic gatekeeper. It is the only component allowed to approve or reject trade risk.

The Risk Governor must evaluate:

- Hard system limits
- Per-trade max loss
- Daily loss limits
- Portfolio exposure
- Symbol, strategy, and sector concentration
- Position sizing
- Options max loss and payoff structure
- Liquidity
- Data freshness
- Broker/account health
- Existing positions and pending orders
- System state
- Kill switch status

The Risk Governor must produce a durable, auditable, machine-readable decision:

- `APPROVED`
- `REJECTED`
- `NEEDS_MORE_DATA`
- `SYSTEM_BLOCKED`

Risk approval must expire. Execution must not rely on stale approvals.

## Execution Guard

The Execution Guard is the final deterministic validation layer immediately before order submission.

Before any Alpaca order can be submitted, the Execution Guard must confirm:

- The opportunity is in `EXECUTION_READY`.
- The latest Risk Governor approval is valid and unexpired.
- The system kill switch is not active.
- Broker connectivity is healthy.
- Account status permits trading.
- Market/session conditions permit the order.
- Market data is fresh enough for the strategy.
- The order exactly matches the approved strategy.
- All order legs are valid.
- Options symbols, expirations, strikes, sides, ratios, and quantities are valid.
- Buying power and max-loss constraints still pass.
- No duplicate active order exists for the same intent.
- The idempotency key is valid.
- The execution validation event has been written to audit storage.

If any check fails, the order must not be submitted.

## Alpaca Boundaries

### Alpaca MCP

Alpaca MCP may be used for controlled, auditable broker-related context and tool interactions when explicitly allowed by implementation policy.

Alpaca MCP must not be exposed to agents as a direct order execution path.

Every Alpaca MCP call must be logged with:

- Calling component
- Purpose
- Request metadata
- Response metadata
- Timestamp
- Linked opportunity or position, when applicable

### Alpaca Trading API

The Alpaca Trading API is the only permitted runtime path for order submission, modification, or cancellation.

It may be called only by deterministic execution services after Risk Governor and Execution Guard approval.

### Alpaca CLI

The Alpaca CLI may be used for development, diagnostics, administrative inspection, or manual operational workflows.

It must not be used by autonomous agents or runtime orchestration to place, modify, or cancel orders.

## Opportunity Lifecycle

The intended lifecycle is:

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

State transitions must be enforced by deterministic application code.

Every transition must include:

- Previous state
- New state
- Actor
- Timestamp
- Reason
- Required evidence references
- Validation result
- Idempotency key, where applicable

Invalid transitions must be rejected and audited.

Expected rejection or failure states include:

- `REJECTED_BY_HADES`
- `REJECTED_BY_RISK`
- `REJECTED_BY_EXECUTION_GUARD`
- `DATA_STALE`
- `BROKER_UNAVAILABLE`
- `KILL_SWITCH_ACTIVE`
- `EXECUTION_FAILED`
- `CANCELLED`
- `EXPIRED`

## Options Support

ORACLE X must support options as first-class trade structures.

Required strategy support includes:

- Calls
- Puts
- Vertical spreads
- Straddles
- Strangles
- Iron condors
- Defined-risk multi-leg combinations

Each options strategy must preserve:

- Underlying symbol
- Contract symbol
- Call or put
- Expiration
- Strike
- Side
- Quantity
- Ratio
- Position intent
- Greeks
- Implied volatility
- Net debit or credit
- Max profit
- Max loss
- Break-even values where applicable

Multi-leg orders must be represented explicitly. They must not be flattened into free-form text.

## Audit And Replay

ORACLE X must be able to answer:

"Why did this trade happen?"

The system must preserve enough information to reconstruct:

- Market evidence
- Agent decisions
- Featherless inference requests and responses
- MCP calls
- Quantitative calculations
- Strategy selection
- Stress tests
- Risk evaluation
- Execution Guard validation
- Alpaca order request
- Alpaca order response
- Fills
- Position lifecycle
- Exit rationale
- Final outcome
- Autopsy
- Lessons learned

Audit records should be append-only wherever practical. Corrections should be recorded as new events, not silent mutations of history.

## Featherless Inference

Featherless is the intended first-class inference provider.

The implementation must include:

- A provider adapter interface
- A Featherless adapter
- Configurable base URL
- Server-side API key handling
- Model selection per agent or task
- Request timeout configuration
- Retry policy for transient failures
- Structured response parsing
- Error classification
- Prompt and response traceability
- Token or usage accounting when available
- Secret redaction
- Failure behavior that does not bypass deterministic controls

Inference failure must not authorize execution.

## Database Expectations

PostgreSQL/Supabase is expected to be the durable source of truth.

The schema must support:

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
- Broker reconciliation
- Autopsies
- Memory records
- System state
- Kill switch events

The database design must include appropriate enums, foreign keys, constraints, indexes, timestamps, idempotency keys, and auditability guarantees.

## Security Requirements

Secrets must never be committed.

Runtime credentials must remain server-side, including:

- Alpaca API credentials
- Featherless API credentials
- Supabase service credentials
- Any broker, data-provider, or MCP credentials

The frontend must not receive broker secrets or unrestricted service-role credentials.

The system must distinguish paper trading from live trading. Live trading must require explicit configuration and protective controls.

Logs and inference traces must redact secrets, tokens, account identifiers where appropriate, and sensitive request headers.

## Testing Requirements

The implementation must include tests for:

- Deterministic quantitative services
- State-machine transitions
- Risk Governor decisions
- Execution Guard validations
- Options strategy representation
- Featherless adapter behavior
- Alpaca adapter behavior
- MCP integration boundaries
- Database migrations and constraints
- Audit/replay reconstruction
- Position reconciliation
- Paper-trading smoke flows

Adversarial tests must prove that AI agents cannot bypass deterministic controls or directly place, modify, or cancel Alpaca orders.

## Implementation Rules For Codex

When working on ORACLE X, Codex must:

- Read this file before implementation work.
- Preserve the architecture described here unless explicitly instructed otherwise.
- Prefer deterministic controls over agent discretion.
- Keep changes scoped and auditable.
- Avoid introducing direct broker execution paths from agent code.
- Avoid storing secrets in source files.
- Add or update tests when implementing risk, execution, state, or broker behavior.
- Stop and ask for approval before weakening any safety boundary in this document.

This file is not application code. It is the baseline implementation contract for the repository.
