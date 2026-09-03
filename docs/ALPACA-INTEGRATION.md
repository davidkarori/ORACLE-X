# ORACLE X — Alpaca Integration

## Three distinct roles

### Alpaca MCP
Agent-facing market research access through Hermes mediation. Use explicit allowlists.

Allowed research categories:
- assets;
- stock data;
- options data;
- news.

The application records the requesting agent, arguments, result metadata, latency and success/failure. Trading, order, position mutation, exercise and account-configuration tools are forbidden.

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
