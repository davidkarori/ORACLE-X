# ORACLE X — Alpaca Integration

## Three distinct roles

### Alpaca MCP
Agent-facing market and account/tool access. Use explicit allowlists.

Suggested permissions:
- ATHENA: market data, news, account/positions; no execution.
- HADES: market/news/positions; no execution.
- HERMES: options chain/snapshots/account/positions; no execution.
- MORPHEUS: market/positions/options; no execution.

### Alpaca Trading API
Application-controlled execution. Only the execution adapter may place orders.

### Alpaca CLI
Operational interface for health checks, paper trading smoke tests, diagnostics, reconciliation and scripts/CI/demo automation.

## Options

Support multi-leg orders where appropriate. Represent each strategy as explicit legs.

The system must not infer successful execution from the request response alone; it must reconcile broker state.

## Idempotency

Generate a deterministic/unique `client_order_id` for every intended submission.

Before retry:
1. check local submission record;
2. query broker status;
3. reconcile;
4. submit only if the original submission is confirmed absent/failed.

## Environment

ALPACA_API_KEY
ALPACA_API_SECRET
ALPACA_TRADING_BASE_URL
ALPACA_DATA_BASE_URL
ALPACA_PAPER_TRADE=true

For the hackathon, paper trading is mandatory in development/demo.
