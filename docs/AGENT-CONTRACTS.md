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
Role: options strategy structurer.

Question: “Given the surviving thesis, what is the best defined-risk expression?”

Consumes surviving thesis, options chain/snapshot, deterministic Greeks/IV/liquidity and account/risk constraints.

Produces strategy type, explicit option legs, entry assumptions, max risk, target/reward, invalidation and rationale.

Must not execute.

## MORPHEUS
Role: stress tester.

Question: “Under what scenarios does the trade break?”

Consumes proposed strategy and deterministic scenario inputs.

Produces stress scenarios, expected behavior, loss/risk observations, failure conditions, resilience score and recommendation.

Must not execute.

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
