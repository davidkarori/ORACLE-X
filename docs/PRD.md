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
4. Hermes constructs a defined-risk options expression.
5. Morpheus stress-tests the strategy.
6. Deterministic Risk Governor evaluates hard constraints.
7. Execution Guard performs the final mechanical check.
8. Alpaca executes only after approval.
9. ORACLE X monitors the position.
10. On exit, ORACLE X performs a trade autopsy and stores lessons.

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
