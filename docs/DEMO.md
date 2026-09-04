# ORACLE X Demo Runbook

## Safe local start

```powershell
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open `http://127.0.0.1:8000`.

All API routes require a bearer token signed with `JWT_SECRET`. For a local browser demo, create an operator token outside the repository and enter it when the War Room prompts. Never paste real secrets into source files.

Without credentials, the War Room runs an explicitly labelled deterministic fixture. It demonstrates contracts, lifecycle transitions, quantitative calculations, Risk Governor gates, the Execution Guard and replay without contacting a broker.

## Connected analysis

Create `.env` from `.env.example` and set:

```text
FEATHERLESS_API_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
```

Leave all paper and execution safety settings at their defaults. A connected run uses Featherless for typed committee decisions, Alpaca API for account/stock/options evidence, and Alpaca MCP for visibly audited read-only stock, option and news research.

## Paper execution

Paper execution requires all of the following:

- `TRADING_MODE=paper`
- `LIVE_TRADING_ENABLED=false`
- `ALPACA_PAPER_TRADE=true`
- the Alpaca URL contains `paper-api.alpaca.markets`
- `EXECUTION_ENABLED=true`
- the UI execution checkbox is selected
- the bearer token has `operator` or `admin` role
- evidence came from Alpaca, not fixtures
- every advisory decision came from Featherless, not fixtures
- every Risk Governor and Execution Guard check passes

The adapter uses a deterministic economic-intent `client_order_id`, records the full request and raw broker response, then reconciles by `client_order_id`. Options do not support extended-hours trading. Unknown broker state blocks the flow instead of blindly retrying.

## Read-only Alpaca MCP

The sample configuration at `config/alpaca-mcp.readonly.json` starts Alpaca's official MCP server with only `assets`, `stock-data`, `options-data` and `news` toolsets. The mutation-capable `trading`, `watchlists` and account-configuration tools are deliberately absent. The application also enforces an exact read-tool allowlist.

Fixture mode can safely demonstrate the complete lifecycle through `LEARNED`. Its simulated submission, fill, position and exit events are explicitly marked and never contact Alpaca.

## CLI evidence

After installing Alpaca CLI and setting paper credentials in the current shell:

```powershell
./scripts/alpaca_cli_smoke.ps1
```

The script performs diagnostics and read-only account, clock and market-data checks. It refuses to run when `ALPACA_LIVE_TRADE=true`.
