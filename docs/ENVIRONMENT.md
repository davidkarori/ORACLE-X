# ORACLE X — Environment Contract

Copy `.env.example` to `.env` for local development. Never commit `.env`.

## Runtime

APP_ENV=development
TRADING_MODE=paper
LOG_LEVEL=INFO

## Database

ORACLE_DB_PATH=oracle_x.db
DATABASE_URL=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

When `DATABASE_URL` starts with `postgresql://` or `postgres://`, the runtime uses PostgreSQL. Otherwise it preserves the SQLite local/test implementation. Server-only: `DATABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

## Featherless

FEATHERLESS_API_KEY=
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
FEATHERLESS_MODEL_ATHENA=
FEATHERLESS_MODEL_HADES=
FEATHERLESS_MODEL_HERMES=
FEATHERLESS_MODEL_MORPHEUS=
FEATHERLESS_TEMPERATURE=0.2
FEATHERLESS_TIMEOUT_SECONDS=30

## Alpaca

ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_TRADING_BASE_URL=
ALPACA_DATA_BASE_URL=
ALPACA_PAPER_TRADE=true

## Application

JWT_SECRET=
CORS_ORIGINS=

## Optional operational

REDIS_URL=
MCP_SERVER_URL=
MCP_TIMEOUT_SECONDS=15
ALPACA_TOOLSETS=assets,stock-data,options-data,news

## Rules

- TRADING_MODE must default to `paper`.
- ALPACA_PAPER_TRADE must default to `true`.
- Production/live trading is not part of the initial hackathon implementation.
- Frontend receives public configuration only.
- Server secrets are never serialized into API responses.
- Mutation-capable MCP toolsets are rejected at startup.
