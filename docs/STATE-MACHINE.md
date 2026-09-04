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

## State ownership

- INVESTIGATING: Athena and Hades may request evidence through shared read-only MCP infrastructure.
- THESIS_CREATED: Athena's typed thesis is valid.
- THESIS_CHALLENGED: Hades has continued the thesis or its requested revision has survived review.
- STRATEGY_SELECTED: Hermes' advisory family has been independently validated and converted into actual legs by deterministic services.
- STRESS_TESTED: the Stress Engine has calculated scenarios and Morpheus has returned PASS or CAUTION. MORPHEUS REJECT transitions to REJECTED before risk evaluation.
- RISK_EVALUATED through EXECUTION_READY: deterministic Risk Governor and Execution Guard ownership is unchanged.
- AUTOPSY: the separate Autopsy Service reconstructs the completed record.
- LEARNED: the Learning Service stores advisory-only memory with zero execution authority.

## Failure paths

Agent/external dependency failures can lead to FAILED where appropriate. Hades, Morpheus, Risk Governor and Execution Guard may lead to REJECTED at their permitted gates.

Fixture mode may simulate the post-submission path for demonstration. Every simulated event is marked and no broker request is made. Connected execution stops at SUBMITTED until real broker reconciliation confirms later states.

## Invariants

- No transition without evidence.
- Invalid transitions are rejected.
- Every transition creates an oracle event.
- Broker state is reconciled before retrying unknown submissions.
- Database state must never claim FILLED solely because an order was submitted.
