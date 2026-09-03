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
│   │   ├── api/
│   │   ├── agents/
│   │   ├── domain/
│   │   ├── execution/
│   │   ├── integrations/
│   │   ├── risk/
│   │   ├── state/
│   │   ├── events/
│   │   ├── persistence/
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   └── package.json
├── supabase/
│   ├── migrations/
│   └── seed.sql
└── tests/
    ├── integration/
    └── e2e/
```

Codex may refine internal folder names while preserving the architectural boundaries.
