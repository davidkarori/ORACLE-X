# ORACLE X — Agent Contracts

## ATHENA
Role: opportunity intelligence.

Question: “Is there a statistically/fundamentally interesting opportunity?”

Consumes market snapshot, news/evidence, account/position context and deterministic indicators.

Produces opportunity assessment, thesis, confidence, supporting evidence, invalidation conditions and risks.

May request and read relevant evidence through the shared read-only MCP adapter. Must not execute.

## HADES
Role: adversarial critic.

Question: “Assume Athena is wrong. Why?”

Consumes Athena's structured thesis plus independent evidence.

Produces strongest counterarguments, fatal objections, survivable objections, missing evidence and a CONTINUE/REVISE/REJECT recommendation.

May request and read relevant evidence through the shared read-only MCP adapter. Must not execute or authorize risk.

## HERMES
Role: options strategy advisor.

Question: “Which defined-risk strategy family best expresses the surviving thesis?”

Consumes the surviving typed thesis, Hades objections, deterministic market context and configured risk profile.

Produces a typed advisory recommendation for LONG_CALL, LONG_PUT, BULL_CALL_SPREAD, BEAR_PUT_SPREAD or IRON_CONDOR, plus rationale, directional intent and structural intent.

Must not select authoritative contracts, strikes, expiration, quantities or prices; calculate Greeks, volatility, max loss/profit, breakevens, P&L, exposure or position sizing; approve risk; or execute.

## MORPHEUS
Role: pre-risk stress-test interpreter.

Question: “What do the deterministic stress scenarios reveal about failure risk?”

Consumes the normalized deterministic strategy and immutable Stress Engine outputs.

Produces scenario interpretation, break-condition commentary and a PASS/CAUTION/REJECT verdict.

REJECT blocks the proposal before Risk Governor evaluation. PASS and CAUTION do not approve risk. Morpheus must not change deterministic stress values or execute.

## Shared MCP infrastructure

MCP is shared read-only research infrastructure, not an agent identity. The adapter owns allowlists, call logging and mutation denial. No agent may use MCP to place, modify, cancel, exercise or close a broker order or position.

## Deterministic services

The Strategy Engine validates Hermes' advisory family and constructs actual legs. The Quant Service calculates every execution-critical value. The Stress Engine generates scenario P&L, break conditions and severity without LLM arithmetic.

## Post-trade services

The Autopsy Service reconstructs the completed decision and outcome record and records what worked and failed. The Learning Service creates advisory-only memory from that autopsy. Neither service can approve or execute a trade, and memory cannot alter execution permissions.

## Shared contract requirements

Every output:
- Pydantic model;
- schema version;
- agent version;
- prompt version;
- timestamp;
- decision;
- confidence;
- evidence references;
- assumptions;
- risks;
- invalidation conditions.

Agent output is advisory evidence, never an execution authorization.
