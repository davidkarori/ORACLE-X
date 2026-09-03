# ORACLE X — Database Contract

PostgreSQL/Supabase is the source of truth.

Canonical migration: `supabase/migrations/001_initial_schema.sql`

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
