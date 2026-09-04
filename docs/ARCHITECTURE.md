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
        +--> Shared Read-only MCP Adapter --> Alpaca MCP
        |
        +--> Strategy Engine / Quant Service
        |
        +--> Stress Engine --> MORPHEUS interpretation
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
        |
        +--> Autopsy Service --> Learning Service

## Component responsibilities

### Frontend
Presentation only. It never holds broker or Featherless secrets.

### API/orchestrator
Coordinates lifecycle, validates commands, starts agent runs, persists events and exposes read APIs.

### Agent runtime
Runs typed Featherless contracts for the canonical committee. Athena forms the thesis, Hades challenges it, Hermes recommends a defined-risk strategy family, and Morpheus interprets deterministic stress outputs before risk evaluation. Agent code never receives broker mutation tools.

### Featherless adapter
OpenAI-compatible client targeting https://api.featherless.ai/v1. The adapter owns provider-specific concerns and records inference traces.

### Alpaca MCP adapter
Provides shared, strictly allowlisted stock, options and news research. Athena and Hades may request relevant evidence through the adapter. It performs the MCP handshake, records metadata for every call and exposes no execution tool. MCP is infrastructure, not an agent role.

### Strategy Engine and Quant Service
The Strategy Engine independently validates Hermes' family recommendation and constructs normalized option legs. The Quant Service calculates all prices, Greeks, volatility, max loss/profit, breakevens, exposure, position sizing and other execution-critical arithmetic.

### Stress Engine and Morpheus
The deterministic Stress Engine calculates scenario P&L, break conditions and severity. Morpheus interprets those immutable outputs and returns PASS, CAUTION or REJECT before the Risk Governor. REJECT blocks the proposal; no verdict grants risk approval.

### Risk Governor
Hard safety boundary. Returns APPROVE/REJECT with reason codes and measured values.

### Execution Guard
Final mechanical gate.

### Alpaca execution adapter
Only component permitted to submit broker orders.

### Event store
SQLite supports local/fixture work. PostgreSQL/Supabase is selected by `DATABASE_URL` for deployed use. `oracle_events`, execution-intent uniqueness and advisory memory preserve durable replay semantics.

### Autopsy Service
Reconstructs the completed thesis, objections, strategy, stress, risk, execution and outcome records, then records what worked and failed.

### Learning Service
Creates auditable, advisory-only memory from completed autopsies. Memory may enrich future agent context but has zero execution authority.

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
