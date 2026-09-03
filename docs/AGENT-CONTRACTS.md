# ORACLE X — Agent Contracts

## ATHENA
Role: opportunity intelligence.

Question: “Is there a statistically/fundamentally interesting opportunity?”

Consumes market snapshot, news/evidence, account/position context and deterministic indicators.

Produces opportunity assessment, thesis, confidence, supporting evidence, invalidation conditions and risks.

Must not execute.

## HADES
Role: adversarial critic.

Question: “Assume Athena is wrong. Why?”

Consumes Athena's structured thesis plus independent evidence.

Produces strongest counterarguments, missing evidence, contradiction signals, thesis survivability, confidence adjustment and recommendation to continue/reject.

Must not execute.

## HERMES
Role: coordination and auditable tool mediator.

Question: “Is the research complete, traceable and safe to pass into the committee?”

Consumes allowlisted read-only MCP call results and their audit metadata.

Produces a research summary, tool references, data gaps and a READY/BLOCKED recommendation.

Must not choose authoritative quantities, approve risk or execute.

## MORPHEUS
Role: post-trade autopsy and learning.

Question: “What should future committees learn from this completed outcome?”

Consumes the immutable thesis, objections, deterministic strategy/stress/risk records and final position outcome.

Produces what worked, what failed, wrong assumptions, lessons and a RETAIN/REVISE/RETIRE recommendation.

Must not alter history, approve future trades or execute. Stored memory is advisory only.

## Deterministic strategy and stress services

The Strategy Engine selects and validates supported structures from the surviving typed thesis and risk profile. The Quant Service calculates every execution-critical value. The Stress Engine generates scenario P&L, break conditions, severity and PASS/CAUTION/REJECT without LLM arithmetic.

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
