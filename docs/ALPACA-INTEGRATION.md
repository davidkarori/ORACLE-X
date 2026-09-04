# ORACLE X — Alpaca Integration

## Three distinct roles

### Alpaca MCP
Shared read-only market research infrastructure. Athena and Hades may request relevant evidence through the adapter. Use explicit allowlists.

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

Multi-leg paper orders use Alpaca's signed limit-price convention: positive prices represent net debits and negative prices represent net credits. Credit structures such as `IRON_CONDOR` must therefore submit a negative `limit_price`.

## Idempotency

Generate a deterministic `client_order_id` from an economic-intent fingerprint covering the paper account namespace, symbol, strategy family, expiration, legs, quantities, price intent and approved risk policy. Equivalent active intents are rejected before broker submission, including after a restart.

Before retry:
1. check local submission record;
2. query broker status;
3. reconcile;
4. submit only if the original submission is confirmed absent/failed.

If a submission times out or returns an unknown state, ORACLE X queries Alpaca by `client_order_id` and records the lookup result. Unknown or mismatched reconciliation blocks further autonomous execution.

## Environment

ALPACA_API_KEY
ALPACA_API_SECRET
ALPACA_TRADING_BASE_URL
ALPACA_DATA_BASE_URL
ALPACA_PAPER_TRADE=true
ALPACA_MIN_OPTIONS_LEVEL=3

For the hackathon, paper trading is mandatory in development/demo.
