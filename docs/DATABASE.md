# ORACLE X — Database Contract

PostgreSQL/Supabase is the source of truth.

Migrations are applied in numeric order under `supabase/migrations/`. Migration `003_runtime_persistence.sql` adds runtime workflow snapshots, unique execution intents, globally ordered events and append-only learning memory without rewriting the original schema.

## Canonical tables

- users
- portfolios
- risk_policies
- market_snapshots
- opportunities
- trades
- agent_decisions
- inference_traces
- risk_evaluations
- trade_legs
- alpaca_orders
- execution_events
- positions
- oracle_events
- risk_events
- mcp_tool_calls
- trade_autopsies
- oracle_memory
- system_state
- workflow_runs
- execution_intents

## Important audit data

### inference_traces
Provider/model/endpoint/request ID/prompt version/input/output/token usage/latency.

### mcp_tool_calls
Agent/tool/status/arguments/result/latency.

### oracle_events
Lifecycle event type, entity references, payload, timestamps and correlation IDs.

### agent_decisions
Structured agent outputs plus evidence, risks, hashes and version metadata.

### risk_evaluations
Deterministic policy version, decision, reason codes and measured values.

### alpaca_orders
Broker order ID, client order ID, class/type/prices/status/raw response.

## Security

API keys never belong in the database schema. Production deployment must add appropriate RLS/authorization policies.
