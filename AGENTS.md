# ORACLE X — Codex Engineering Contract

## 1. Mission

ORACLE X is an autonomous AI trading/investment committee for the Alpaca AI Trading Agents Hackathon.

The product must demonstrate:
- multi-agent investment reasoning;
- Featherless AI inference;
- Alpaca MCP market/tool access;
- deterministic quantitative/risk controls;
- controlled Alpaca execution;
- explainability and evidence;
- complete auditability and decision replay;
- trade autopsy and learning.

The system is designed for paper trading during development and the hackathon demo.

## 2. Non-negotiable architecture

### AI reasoning
Featherless is the first-class LLM inference provider.

Four agents:
- ATHENA — opportunity intelligence and thesis formation.
- HADES — adversarial critic that may require revision or rejection.
- HERMES — options strategy advisor for defined-risk strategy family and structural intent.
- MORPHEUS — pre-risk stress-test interpreter that returns PASS, CAUTION or REJECT.

LLMs interpret evidence and produce structured advisory decisions. They do NOT own deterministic financial calculations, construct executable option legs, approve risk or authorize execution.

HERMES may recommend only these strategy families: LONG_CALL, LONG_PUT, BULL_CALL_SPREAD, BEAR_PUT_SPREAD and IRON_CONDOR. The deterministic Strategy Engine must independently validate the recommendation and construct the actual structure.

MORPHEUS reviews deterministic stress outputs before the Risk Governor. A MORPHEUS REJECT verdict blocks the proposal, but PASS and CAUTION are advisory inputs and never constitute risk approval.

### Market/tool layer
Alpaca MCP is shared, read-only research infrastructure. It is not the identity or primary responsibility of any agent.

Alpaca MCP tool access must be allowlisted per agent. ATHENA and HADES may request and read relevant evidence only through the safety-bounded adapter. No agent receives a mutation-capable MCP tool.

### Execution layer
Alpaca Trading API is the controlled execution interface.

Alpaca CLI is used for operational automation, diagnostics, paper smoke tests, reconciliation and demo/CI tasks where appropriate.

### Safety boundary
The path is:

Shared read-only evidence → ATHENA thesis → HADES challenge → HERMES strategy-family recommendation → deterministic Strategy Engine and Quant Service → deterministic Stress Engine → MORPHEUS stress verdict → deterministic Risk Governor → Execution Guard → idempotency check → Alpaca execution adapter → broker confirmation → reconciliation → event/audit log

No LLM may directly place, modify or cancel an order.

## 3. Risk Governor

The Risk Governor is deterministic application code.

Never ask an LLM to decide whether a trade violates a hard risk limit.

Risk policies must be stored/configurable and evaluated mechanically.

At minimum support:
- maximum position/notional exposure;
- maximum portfolio risk;
- maximum loss per trade;
- maximum number of open trades;
- minimum reward/risk;
- option liquidity/spread constraints;
- maximum contract quantity;
- expiration constraints;
- concentration limits;
- paper/live mode gate;
- system HALTED/PAUSED gate;
- position reconciliation gate.

A rejected trade must include machine-readable reason codes.

## 4. Execution Guard

Every proposed order must be validated again immediately before broker submission.

Execution Guard must reject:
- missing approval;
- invalid state;
- failed risk evaluation;
- live mode when live trading is disabled;
- malformed legs;
- missing required prices/quantities;
- duplicate client_order_id;
- stale market evidence;
- position mismatch;
- halted system.

Unknown broker submission status must be reconciled before any retry.

## 5. State machine

Canonical opportunity lifecycle:

DETECTED → INVESTIGATING → THESIS_CREATED → THESIS_CHALLENGED → STRATEGY_SELECTED → STRESS_TESTED → RISK_EVALUATED → APPROVED → EXECUTION_READY → SUBMITTED → FILLED → POSITION_OPEN → POSITION_MONITORING → EXIT_SIGNAL → EXIT_EXECUTION → POSITION_CLOSED → AUTOPSY → LEARNED

Alternative terminal/failure states: FAILED, REJECTED.

Every transition requires evidence and is recorded as an oracle event.

Invalid transitions must be rejected.

## 6. Agent contracts

Every agent input/output must use typed Pydantic models.

Do not pass arbitrary prose between agents as the authoritative contract.

Each decision must contain:
- decision;
- confidence;
- thesis/summary;
- evidence references;
- risks/invalidating conditions;
- assumptions;
- timestamp;
- agent version;
- prompt version.

Use JSON structured output from Featherless.

## 7. Quantitative integrity

Python/application code independently validates strategy-family recommendations, constructs actual option legs, runs stress scenarios, and calculates exact quantities: market prices, indicators, returns, volatility, IV, Greeks, spreads, reward/risk, max loss, max profit, breakevens, exposure, scenario P&L and position sizing.

The model may interpret these values, compare evidence and explain them.

Never rely on LLM arithmetic for an execution-critical value.

## 8. Post-trade services

Post-trade autopsy and learning are separate from the four-agent pre-risk committee.

The Autopsy Service reconstructs the immutable thesis, objections, strategy, stress results, risk decision, execution record and outcome, then records what worked and what failed.

The Learning Service converts completed autopsy evidence into advisory-only memory. Memory may influence future agent context, but it has zero execution authority and may never bypass the Risk Governor or Execution Guard.

## 9. Options

ORACLE X is options-aware. Represent multi-leg strategies explicitly, including spreads, straddles/strangles, iron condors and other defined-risk combinations.

Each leg must record contract, underlying, option type, strike, expiration, side, position intent and ratio, plus available Greeks/IV.

## 10. Auditability

Record agent decisions, Featherless inference traces, Alpaca MCP calls, risk evaluations/events, trades/legs/orders/execution events, positions, state transitions, system events, trade autopsies and learning memory.

Decision replay must be possible from stored evidence and event history.

## 11. Security

- Secrets only on the server.
- Never expose API keys to the frontend.
- Never commit .env files.
- Provide .env.example only.
- Default to paper trading.
- Fail closed when critical dependencies are unavailable.
- Validate external payloads before use.

## 12. Database

PostgreSQL is the source of truth. Use migrations under `supabase/migrations/`.

Canonical tables: users, portfolios, risk_policies, market_snapshots, opportunities, trades, agent_decisions, inference_traces, risk_evaluations, trade_legs, alpaca_orders, execution_events, positions, oracle_events, risk_events, mcp_tool_calls, trade_autopsies, oracle_memory, system_state.

## 13. Testing

Financial/risk logic requires automated tests. Minimum coverage includes each agent contract, Risk Governor, state machine, Execution Guard, Alpaca adapter, idempotency, reconciliation and failure/timeout paths.

A test must prove duplicate order submission cannot occur.

## 14. Engineering behavior for Codex

Before changing architecture:
1. Read this file.
2. Read relevant docs.
3. Inspect the repository.
4. Prefer small, reviewable changes.
5. Run tests after changes.
6. Never replace a designed safety boundary with a shortcut.
7. Update documentation when behavior changes.

Do not invent missing business rules. Put unresolved items in `docs/DECISIONS.md`.

## 15. Definition of done

A feature is done when implementation, typed contracts, failure handling, tests, relevant audit/event behavior and documentation are present, secrets are protected, and paper-trading safety remains intact.
