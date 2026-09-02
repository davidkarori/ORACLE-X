# ORACLE X

ORACLE X is a trading intelligence and execution-control system designed around one non-negotiable rule:

AI agents may reason, investigate, challenge, summarize, and learn, but they must never directly place, modify, or cancel broker orders.

All execution authority belongs to deterministic application services guarded by a Risk Governor, an Execution Guard, durable audit records, and explicit broker boundaries.

## Current Status

This repository is in foundation setup.

Implemented repository files:

- `AGENTS.md` - agent governance, safety boundaries, lifecycle, and implementation contract
- `README.md` - project overview and intended build direction

Not implemented yet:

- Backend application
- Frontend War Room
- Supabase schema
- Agent runtime
- Featherless inference adapter
- Alpaca integrations
- Deterministic quantitative services
- Risk Governor
- Execution Guard
- Audit/replay system
- Learning/memory system
- Tests
- Deployment configuration

## Architecture Summary

ORACLE X is intended to combine AI-assisted trading research with deterministic controls.

The system should include:

- Agent-assisted opportunity discovery and critique
- Deterministic quantitative services
- Deterministic risk evaluation
- Deterministic execution validation
- Alpaca paper/live trading integration
- PostgreSQL/Supabase as durable state
- A War Room frontend for visibility and operator control
- Full audit and replay of every trade lifecycle
- Post-trade autopsy and learning memory

## Agent Model

ORACLE X uses named agents with limited authority:

- **Athena** discovers opportunities, synthesizes evidence, and drafts theses.
- **Hades** challenges theses, identifies risks, and records dissent.
- **Hermes** coordinates tool calls, messages, and traceable interactions.
- **Morpheus** performs autopsies, replay analysis, and memory extraction.

Agents are advisory. They do not own execution authority.

See `AGENTS.md` for the full governance contract.

## Deterministic Control Plane

The following must be implemented as deterministic application services:

- Indicators
- Returns
- Volatility
- Implied volatility
- Greeks
- Spreads
- Reward/risk
- Exposure
- P&L
- Position sizing
- Stress calculations
- Risk approval
- Execution validation
- Broker order submission
- Position reconciliation

LLMs may explain these results, but they must not be the source of truth.

## Opportunity Lifecycle

The intended opportunity lifecycle is:

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

State transitions must be enforced by application code and written to durable audit storage.

## Alpaca Integration Boundaries

ORACLE X separates Alpaca responsibilities into three categories:

- **Alpaca MCP**: controlled, auditable broker-related tool interactions.
- **Alpaca Trading API**: deterministic runtime order submission path.
- **Alpaca CLI**: development, diagnostics, and manual operations only.

No AI agent may use any Alpaca path to directly place, modify, or cancel orders.

## Featherless Inference

Featherless is intended to be the first-class inference provider for agent reasoning.

The future implementation should include:

- A provider adapter interface
- A Featherless adapter
- Server-side API key handling
- Model selection per task or agent
- Request and response tracing
- Timeout and retry behavior
- Failure handling that fails closed
- Redaction of secrets and sensitive data

Inference output must remain advisory and auditable.

## Database Direction

PostgreSQL/Supabase is expected to be the durable source of truth.

The schema should support:

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

## Security Direction

Secrets must remain server-side and must never be committed.

Protected credentials include:

- Alpaca API credentials
- Featherless API credentials
- Supabase service credentials
- Broker, market-data, and MCP credentials

Live trading must require explicit configuration and protective controls. Paper trading should be the default implementation target.

## Recommended Build Order

1. Complete repository foundation docs.
2. Define environment and secrets model.
3. Create initial Supabase schema.
4. Implement the state machine.
5. Implement deterministic quantitative services.
6. Implement Featherless inference adapter.
7. Implement agent runtime.
8. Implement Risk Governor.
9. Implement Execution Guard.
10. Implement Alpaca paper-trading adapter.
11. Implement reconciliation and monitoring.
12. Build the War Room frontend.
13. Add audit replay, autopsy, and memory.
14. Add adversarial and end-to-end tests.
15. Prepare practical deployment.

## Implementation Rule

Before adding application code, contributors and AI assistants must read `AGENTS.md`.

Any change that weakens the separation between AI reasoning and deterministic execution requires explicit approval.
