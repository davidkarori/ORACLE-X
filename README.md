# ORACLE X

### The AI Investment Committee That Doesn't Trade on Blind Faith

ORACLE X is an autonomous, multi-agent AI trading intelligence system built for the **Alpaca AI Trading Agents Hackathon**.

Instead of trusting a single AI model to make a trading decision, ORACLE X creates an investment committee where specialized agents reason about an opportunity, challenge assumptions, construct a defined-risk options strategy, and stress-test the proposal.

A deterministic **Risk Governor** then decides whether the proposed trade is actually allowed to reach the market.

> **AI builds the case. Deterministic software governs it. Alpaca executes it. Every decision can be replayed.**

## The Committee

| Agent | Role | Core question |
|---|---|---|
| **ATHENA** | Opportunity Intelligence | Is there an interesting opportunity? |
| **HADES** | Adversarial Critic | Assume Athena is wrong. Why? |
| **HERMES** | Options Strategist | What is the best defined-risk expression? |
| **MORPHEUS** | Stress Tester | Under what scenarios does the trade break? |

## Safety Architecture

```text
Market Evidence
      ↓
ATHENA → HADES → HERMES → MORPHEUS
      ↓
Structured Contracts
      ↓
Deterministic Risk Governor
      ↓
Execution Guard
      ↓
Alpaca Execution Adapter
      ↓
Alpaca
```

**No LLM may directly place, modify or cancel an order.**

The hackathon implementation uses **paper trading only**.

## Technology

- **Featherless** — AI inference
- **Alpaca MCP** — agent-facing market/research tools
- **Alpaca Trading API** — controlled execution
- **Alpaca CLI** — diagnostics, automation and reconciliation
- **Python / FastAPI / Pydantic** — backend and typed contracts
- **PostgreSQL / Supabase** — system of record
- **Web frontend** — ORACLE X War Room

## Decision Replay

Every major decision is recorded:

```text
Opportunity
  ↓
Evidence
  ↓
ATHENA Thesis
  ↓
HADES Critique
  ↓
HERMES Strategy
  ↓
MORPHEUS Stress Test
  ↓
Risk Evaluation
  ↓
Execution
  ↓
Outcome
  ↓
Trade Autopsy
  ↓
Learning
```

The system is designed to answer **why a trade was made, why it was rejected, and what was learned afterward**.

## Repository

See `AGENTS.md` for the non-negotiable engineering contract and `CODEX-INSTRUCTIONS.md` for the implementation handoff. The canonical database migration is under `supabase/migrations/001_initial_schema.sql`.

## Current status

Architecture and repository handoff are established. Implementation proceeds in staged milestones, beginning with the foundation and Featherless AI Engine.

## Core philosophy

> **Don't trust one AI. Convene a committee.**

> **AI builds the case. The Governor decides whether the case is allowed to touch the market.**
