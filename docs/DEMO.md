# ORACLE X Demo Runbook

## Safe local start

```powershell
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open `http://127.0.0.1:8000`.

Without credentials, the War Room runs an explicitly labelled deterministic fixture. It demonstrates contracts, lifecycle transitions, quantitative calculations, Risk Governor gates, the Execution Guard and replay without contacting a broker.

## Connected analysis

Create `.env` from `.env.example` and set:

```text
FEATHERLESS_API_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
```

Leave all paper and execution safety settings at their defaults. A connected run uses Featherless for four typed advisory decisions and Alpaca for account, stock and options evidence.

## Paper execution

Paper execution requires all of the following:

- `TRADING_MODE=paper`
- `LIVE_TRADING_ENABLED=false`
- `ALPACA_PAPER_TRADE=true`
- the Alpaca URL contains `paper-api.alpaca.markets`
- `EXECUTION_ENABLED=true`
- the UI execution checkbox is selected
- evidence came from Alpaca, not fixtures
- every advisory decision came from Featherless, not fixtures
- every Risk Governor and Execution Guard check passes

The adapter uses a deterministic `client_order_id` and records the intent before submission. Options do not support extended-hours trading.

## Read-only Alpaca MCP

The sample configuration at `config/alpaca-mcp.readonly.json` starts Alpaca's official MCP server with only `account`, `assets`, `stock-data`, `options-data` and `news` toolsets. The `trading` toolset is deliberately absent, so agents cannot receive order mutation tools.

## CLI evidence

After installing Alpaca CLI and setting paper credentials in the current shell:

```powershell
./scripts/alpaca_cli_smoke.ps1
```

The script performs diagnostics and read-only account, clock and market-data checks. It refuses to run when `ALPACA_LIVE_TRADE=true`.
