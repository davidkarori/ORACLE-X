# ORACLE X — Product Requirements Document

## Product
ORACLE X — Autonomous AI Trading Intelligence Committee

## Problem
Most AI trading demos reduce trading to one model generating one recommendation. That makes the reasoning fragile, difficult to audit and unsafe to connect to execution.

ORACLE X treats a trade as a committee decision.

## Core experience

1. Detect an opportunity.
2. Athena builds the evidence-backed thesis.
3. Hades attacks the thesis.
4. Hermes recommends a typed, defined-risk options strategy family and structural intent.
5. Deterministic Strategy and Quant services validate the recommendation, construct actual legs and calculate all authoritative numbers.
6. The deterministic Stress Engine calculates scenarios; Morpheus interprets them as PASS, CAUTION or REJECT.
7. Deterministic Risk Governor evaluates hard constraints only if Morpheus has not rejected the proposal.
8. Execution Guard performs the final mechanical check.
9. Alpaca executes only after approval.
10. ORACLE X monitors the position.
11. On exit, the Autopsy Service reconstructs the outcome and the Learning Service stores advisory-only lessons.

## Primary demo story

The War Room should make the committee visible: live opportunity, agent activity, evidence, disagreement, selected strategy, stress scenarios, deterministic risk result, execution status, P&L, audit trail and replay/autopsy.

## Success criteria

The hackathon demo should visibly prove:
- Featherless is actually used for model inference;
- Alpaca MCP is actually used for market/tool access;
- Alpaca execution is controlled by application code;
- no LLM can bypass Risk Governor;
- decisions are explainable;
- rejected trades are explainable;
- the system can replay why a decision happened.

## Non-goals for MVP

- unrestricted live trading;
- unmanaged autonomous capital;
- opaque end-to-end agent execution;
- replacing deterministic calculations with LLM reasoning;
- building a full brokerage product.

## Key differentiator

“ORACLE doesn't ask an LLM whether it should trade. It asks a committee of models to build a case—and then a deterministic Governor decides whether that case is allowed to touch the market.”
