# ORACLE X — System Architecture

## High-level flow

Frontend War Room
        |
        v
API / Orchestrator
        |
        +--> Opportunity Engine
        |
        +--> Agent Runtime
        |      |
        |      +--> ATHENA
        |      +--> HADES
        |      +--> HERMES
        |      +--> MORPHEUS
        |             |
        |             +--> Featherless API
        |
        +--> Read-only MCP Adapter --> Alpaca MCP
        |
        +--> Strategy/Quant/Stress Services
        |      |
        |      +--> Risk Governor
        |      +--> Execution Guard
        |
        +--> Execution Adapter
        |      |
        |      +--> Alpaca Trading API
        |
        +--> PostgreSQL / Supabase
        |
        +--> Event/Audit Stream

## Component responsibilities

### Frontend
Presentation only. It never holds broker or Featherless secrets.

### API/orchestrator
Coordinates lifecycle, validates commands, starts agent runs, persists events and exposes read APIs.

### Agent runtime
Runs typed Featherless contracts. Hermes receives mediated MCP evidence; agent code never receives broker mutation tools.

### Featherless adapter
OpenAI-compatible client targeting https://api.featherless.ai/v1. The adapter owns provider-specific concerns and records inference traces.

### Alpaca MCP adapter
Provides strictly allowlisted stock, options and news research. It performs the MCP handshake, records metadata for every call and exposes no execution tool.

### Quant service
Selects normalized supported option structures and calculates exact market/risk values and stress scenarios in deterministic code.

### Risk Governor
Hard safety boundary. Returns APPROVE/REJECT with reason codes and measured values.

### Execution Guard
Final mechanical gate.

### Alpaca execution adapter
Only component permitted to submit broker orders.

### Event store
SQLite supports local/fixture work. PostgreSQL/Supabase is selected by `DATABASE_URL` for deployed use. `oracle_events`, execution-intent uniqueness and advisory memory preserve durable replay semantics.

## Failure philosophy

Fail closed. If Featherless, Alpaca market data, the database, reconciliation or risk services are unavailable, autonomous new-order execution must not proceed.

## Deployment target

Recommended:
- frontend: Vercel;
- backend: production Python service;
- database: Supabase/PostgreSQL;
- external inference: Featherless;
- broker: Alpaca;
- operational automation: Alpaca CLI.

The architecture must remain portable and not hard-code deployment-provider assumptions into domain logic.
