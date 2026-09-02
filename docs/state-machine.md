# ORACLE X State Machine

This document defines the intended opportunity lifecycle and the enforcement requirements for valid transitions.

State transitions must be deterministic, auditable, and enforced in application code.

## Happy Path

```text
DETECTED
-> INVESTIGATING
-> THESIS_CREATED
-> THESIS_CHALLENGED
-> STRATEGY_SELECTED
-> STRESS_TESTED
-> RISK_EVALUATED
-> APPROVED
-> EXECUTION_READY
-> SUBMITTED
-> FILLED
-> POSITION_OPEN
-> POSITION_MONITORING
-> EXIT_SIGNAL
-> EXIT_EXECUTION
-> POSITION_CLOSED
-> AUTOPSY
-> LEARNED
```

## State Definitions

### DETECTED

An opportunity has been detected from market data, screening, watchlists, alerts, or operator input.

### INVESTIGATING

The opportunity is under investigation. Athena may gather evidence and request deterministic calculations.

### THESIS_CREATED

Athena has produced a structured thesis with linked evidence.

### THESIS_CHALLENGED

Hades has reviewed the thesis and recorded challenges, risks, missing evidence, or dissent.

### STRATEGY_SELECTED

A candidate strategy has been selected and represented in structured form, including trade legs where applicable.

### STRESS_TESTED

Deterministic services have run required stress, payoff, sizing, liquidity, and exposure calculations.

### RISK_EVALUATED

The Risk Governor has evaluated the strategy.

### APPROVED

The Risk Governor has approved the strategy. Approval must be durable and must expire.

### EXECUTION_READY

The opportunity is ready for immediate pre-submit validation by the Execution Guard.

### SUBMITTED

The deterministic execution service has submitted the order to Alpaca through the Alpaca Trading API.

### FILLED

The order has received one or more fills sufficient to establish the intended position.

### POSITION_OPEN

The position is open and reconciled with broker state.

### POSITION_MONITORING

The system is monitoring the open position, market conditions, risk limits, and exit criteria.

### EXIT_SIGNAL

A deterministic or approved advisory process has identified an exit condition.

### EXIT_EXECUTION

The system is validating and executing the exit through deterministic controls.

### POSITION_CLOSED

The broker-reconciled position is closed.

### AUTOPSY

Morpheus or post-trade analysis is evaluating the full lifecycle and outcome.

### LEARNED

Lessons learned have been stored in memory and linked to the trade record.

## Failure And Rejection States

Expected non-happy-path states include:

- `REJECTED_BY_HADES`
- `REJECTED_BY_RISK`
- `REJECTED_BY_EXECUTION_GUARD`
- `DATA_STALE`
- `BROKER_UNAVAILABLE`
- `KILL_SWITCH_ACTIVE`
- `EXECUTION_FAILED`
- `CANCELLED`
- `EXPIRED`

These states must also be audited.

## Transition Requirements

Every transition must record:

- Opportunity identifier
- Previous state
- New state
- Actor or service
- Timestamp
- Reason
- Validation result
- Evidence references
- Idempotency key when applicable

Invalid transitions must be rejected and recorded as failed transition attempts.

## Required Gates

### Before STRATEGY_SELECTED

The system should have:

- Market evidence
- Thesis record
- Hades challenge or explicit challenge waiver
- Structured strategy candidate

### Before STRESS_TESTED

The system should have:

- Strategy legs
- Required market inputs
- Required options data when applicable
- Data freshness metadata

### Before RISK_EVALUATED

The system should have:

- Deterministic calculations
- Stress results
- Position sizing proposal
- Exposure context
- Existing position and pending-order context

### Before APPROVED

The Risk Governor must produce a deterministic decision.

Only an `APPROVED` Risk Governor decision can move an opportunity to `APPROVED`.

### Before EXECUTION_READY

The system must confirm:

- Approval has not expired.
- Strategy has not changed since approval.
- Required audit records exist.
- Kill switch is inactive.

### Before SUBMITTED

The Execution Guard must run immediately before submission and pass.

The execution service must submit through the Alpaca Trading API using an idempotency key.

### Before POSITION_OPEN

The system must reconcile fills and broker position state.

### Before EXIT_EXECUTION

Exit action must pass deterministic validation equivalent to entry execution validation.

## Concurrency And Idempotency

The state machine must prevent:

- Duplicate submissions
- Out-of-order transitions
- Stale approvals
- Strategy mutation after approval without re-review
- Multiple active execution attempts for the same intent
- Agent-side state mutation

Idempotency keys should be required for:

- State transitions that trigger external effects
- Risk approval attempts
- Execution Guard validations
- Alpaca order submissions
- Order modifications
- Order cancellations

## Audit And Replay

The state machine is a core input to audit and replay.

A reviewer should be able to reconstruct:

- Why the opportunity was detected
- What evidence was used
- What Athena proposed
- What Hades challenged
- What strategy was selected
- What calculations were used
- Why risk passed or failed
- Why execution was permitted or blocked
- What broker action occurred
- What fills occurred
- How the position evolved
- Why exit occurred
- What was learned

If the system cannot reconstruct this chain, the implementation is incomplete.
