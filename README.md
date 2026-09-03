# ORACLE X

### The AI Investment Committee That Doesn't Trade on Blind Faith

![ORACLE X paper-trading War Room](assets/oracle-x-cover.png)

ORACLE X is an autonomous, multi-agent AI trading intelligence system built for the **Alpaca AI Trading Agents Hackathon**.

Instead of trusting a single AI model to make a trading decision, ORACLE X creates an investment committee where specialized agents gather evidence, reason about an opportunity, challenge assumptions, and learn from completed outcomes. Deterministic services construct and stress-test the options strategy.

A deterministic **Risk Governor** then decides whether the proposed trade is actually allowed to reach the market.

> **AI builds the case. Deterministic software governs it. Alpaca executes it. Every decision can be replayed.**

## The Committee

| Agent | Role | Core question |
|---|---|---|
| **ATHENA** | Opportunity Intelligence | Is there an interesting opportunity? |
| **HADES** | Adversarial Critic | Assume Athena is wrong. Why? |
| **HERMES** | Research Coordinator | Is the evidence complete, traceable and safe to use? |
| **MORPHEUS** | Trade Autopsy | What should future committees learn from the outcome? |

## Safety Architecture

```text
Alpaca API + read-only MCP evidence
      ↓
HERMES mediation → ATHENA thesis → HADES challenge
      ↓
Deterministic strategy, quant and stress services
      ↓
Deterministic Risk Governor
      ↓
Execution Guard
      ↓
Alpaca Execution Adapter
      ↓
Alpaca
      ↓
Position lifecycle → MORPHEUS autopsy → advisory memory
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
Deterministic Strategy + Stress Test
  ↓
Risk Evaluation
  ↓
Execution
  ↓
Outcome
  ↓
MORPHEUS Trade Autopsy
  ↓
Learning
```

The system is designed to answer **why a trade was made, why it was rejected, and what was learned afterward**.

## Repository

See `AGENTS.md` for the non-negotiable engineering contract and `CODEX-INSTRUCTIONS.md` for the implementation handoff. Database migrations are applied in order from `supabase/migrations/`.

## Current status

A working hackathon vertical slice is implemented. It includes typed Featherless contracts, visible read-only Alpaca MCP research, five deterministic options strategies, quantitative and stress calculations, a full replayable lifecycle through autopsy and learning, SQLite/PostgreSQL persistence, Risk Governor, Execution Guard, idempotent paper-order intent and the War Room interface.

## Judge quick links

- [Demo runbook](docs/DEMO.md)
- [Two-minute video script](docs/VIDEO-SCRIPT.md)
- [Submission brief](docs/SUBMISSION.md)
- [Hackathon presentation](assets/presentation/oracle-x-hackathon-deck.pptx)
- [Safety governance](AGENTS.md)

## Run the War Room

```powershell
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open `http://127.0.0.1:8000`.

The default fixture mode is deterministic, clearly labelled and unable to submit orders. To connect Featherless and Alpaca, copy `.env.example` to `.env`, add server-side credentials, and keep every paper-trading safety setting enabled. See `docs/DEMO.md` for the connected and paper-execution checklist.

## Safety evidence

- Agents return advisory typed contracts and cannot import the broker execution path.
- Risk approval and final execution validation are deterministic.
- Live Alpaca endpoints are rejected during configuration validation.
- Fixture evidence cannot authorize a broker mutation.
- Paper execution is disabled by default and requires an explicit second operator action.
- Audit events are append-only and exposed through a replay endpoint.

Run the focused safety suite with `python -m pytest -q`.

## Core philosophy

> **Don't trust one AI. Convene a committee.**

> **AI builds the case. The Governor decides whether the case is allowed to touch the market.**
