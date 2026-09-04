# ORACLE X — Repository Structure

```text
ORACLE-X/
├── AGENTS.md
├── README.md
├── CODEX-INSTRUCTIONS.md
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── AGENT-CONTRACTS.md
│   ├── RISK-GOVERNOR.md
│   ├── STATE-MACHINE.md
│   ├── FEATHERLESS-INTEGRATION.md
│   ├── ALPACA-INTEGRATION.md
│   ├── DATABASE.md
│   ├── ENVIRONMENT.md
│   ├── PROJECT-STRUCTURE.md
│   └── DECISIONS.md
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── domain.py
│   │   ├── integrations.py
│   │   ├── mcp_adapter.py
│   │   ├── post_trade.py
│   │   ├── quant.py
│   │   ├── store.py
│   │   ├── workflow.py
│   │   ├── main.py
│   │   └── static/
├── config/
│   └── alpaca-mcp.readonly.json
├── supabase/
│   ├── migrations/
│   └── seed.sql
└── tests/
    └── test_workflow.py
```

Codex may refine internal folder names while preserving the architectural boundaries.
