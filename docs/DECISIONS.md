# ORACLE X — Architecture Decisions

## ADR-001: Featherless is the inference provider
Status: accepted.

Reason: required hackathon integration and open-source model inference.

## ADR-002: Alpaca MCP is not the execution authority
Status: accepted.

Reason: agents need tool access, but execution must remain behind deterministic application controls.

## ADR-003: Risk Governor is deterministic
Status: accepted.

Reason: hard risk limits cannot depend on probabilistic model output.

## ADR-004: Paper trading during build/demo
Status: accepted.

Reason: safety and reproducibility.

## ADR-005: PostgreSQL is source of truth
Status: accepted.

Reason: durable audit, state, replay and learning history.

## ADR-006: No direct LLM execution
Status: accepted.

Reason: prevents prompt/model behavior from bypassing risk and execution controls.

Unresolved implementation choices should be added here rather than silently changing the architecture.
