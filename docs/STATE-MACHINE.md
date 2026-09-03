# ORACLE X — State Machine

## States

DETECTED
INVESTIGATING
THESIS_CREATED
THESIS_CHALLENGED
STRATEGY_SELECTED
STRESS_TESTED
RISK_EVALUATED
APPROVED
EXECUTION_READY
SUBMITTED
FILLED
FAILED
POSITION_OPEN
POSITION_MONITORING
EXIT_SIGNAL
EXIT_EXECUTION
POSITION_CLOSED
AUTOPSY
LEARNED
REJECTED

## Canonical path

DETECTED → INVESTIGATING → THESIS_CREATED → THESIS_CHALLENGED → STRATEGY_SELECTED → STRESS_TESTED → RISK_EVALUATED → APPROVED → EXECUTION_READY → SUBMITTED → FILLED → POSITION_OPEN → POSITION_MONITORING → EXIT_SIGNAL → EXIT_EXECUTION → POSITION_CLOSED → AUTOPSY → LEARNED

## Failure paths

Agent/external dependency failures can lead to FAILED where appropriate. Risk Governor can lead to REJECTED.

## Invariants

- No transition without evidence.
- Invalid transitions are rejected.
- Every transition creates an oracle event.
- Broker state is reconciled before retrying unknown submissions.
- Database state must never claim FILLED solely because an order was submitted.
