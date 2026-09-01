# ORACLE X — Deterministic Risk Governor

## Purpose

Convert an AI-generated trade proposal into a mechanically approved or rejected risk decision.

The LLM cannot modify Governor rules at runtime.

## Inputs

- portfolio equity;
- buying power;
- existing exposure;
- proposed legs;
- estimated max loss;
- reward/risk;
- liquidity;
- bid/ask spread;
- expiration;
- concentration;
- open-trade count;
- system state;
- paper/live mode;
- market-data freshness;
- position reconciliation status.

## Required gates

1. System must be ACTIVE.
2. Trading mode must be PAPER for the hackathon build.
3. Position reconciliation must be clean.
4. Proposal must be schema-valid.
5. Required evidence must be fresh.
6. Maximum loss must be within policy.
7. Position/notional exposure must be within policy.
8. Portfolio risk must be within policy.
9. Reward/risk must meet minimum.
10. Liquidity/spread rules must pass.
11. Contract quantity must be within policy.
12. Expiration rules must pass.
13. Concentration rules must pass.
14. Open-trade limit must pass.

## Output

```json
{
  "decision": "APPROVE|REJECT",
  "reason_codes": [],
  "measured_values": {},
  "policy_version": "...",
  "evaluated_at": "...",
  "evidence_refs": []
}
```

## Rule

A trade is approved only if every mandatory gate passes.

Unknown, stale or missing information must fail closed where the information is execution-critical.

## Testing

Each rule must have passing, boundary and failing cases.
