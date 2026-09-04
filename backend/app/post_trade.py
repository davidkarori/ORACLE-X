import uuid

from .domain import (
    AthenaDecision,
    HadesDecision,
    LearningMemory,
    MorpheusDecision,
    TradeAutopsy,
    WorkflowRun,
)


class AutopsyService:
    service_version = "autopsy-v1"

    def create(self, run: WorkflowRun) -> TradeAutopsy:
        if not run.strategy or not run.stress or not run.risk or not run.position:
            raise ValueError("Autopsy requires strategy, stress, risk, and position records")
        athena = next((item for item in reversed(run.decisions) if isinstance(item, AthenaDecision)), None)
        morpheus = next((item for item in reversed(run.decisions) if isinstance(item, MorpheusDecision)), None)
        if not athena or not morpheus:
            raise ValueError("Autopsy requires Athena and Morpheus decisions")
        hades_decisions = [item for item in run.decisions if isinstance(item, HadesDecision)]
        objections = [
            objection
            for decision in hades_decisions
            for objection in [*decision.fatal_objections, *decision.survivable_objections]
        ]
        realized = run.position.realized_pnl
        unrealized = run.position.unrealized_pnl
        execution_status = str((run.broker_order or {}).get("status", run.position.status)).upper()
        what_worked = [
            "Deterministic risk and execution gates remained authoritative",
            f"{run.strategy.strategy_type.value} preserved explicit bounded-risk legs",
        ]
        what_failed: list[str] = []
        wrong_assumptions: list[str] = []
        if realized > 0:
            what_worked.append("The closed position produced a positive realized outcome")
        elif realized < 0:
            what_failed.append("The closed position produced a realized loss")
            wrong_assumptions.append("The thesis did not produce the expected favorable move")
        else:
            what_failed.append("The closed position did not produce a realized return")
        return TradeAutopsy(
            id=str(uuid.uuid4()),
            source_run_id=run.id,
            symbol=run.symbol,
            original_thesis=athena.thesis,
            hades_objections=objections,
            strategy_type=run.strategy.strategy_type,
            stress_recommendation=run.stress.recommendation,
            morpheus_verdict=morpheus.recommendation,
            risk_decision=run.risk.decision,
            execution_outcome=execution_status,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            outcome_summary=(
                f"{run.symbol} {run.strategy.strategy_type.value} closed with realized P&L {realized:.2f}; "
                f"stress was {run.stress.recommendation} and Morpheus returned {morpheus.recommendation}."
            ),
            what_worked=what_worked,
            what_failed=what_failed,
            wrong_assumptions=wrong_assumptions,
        )


class LearningService:
    service_version = "learning-v1"

    def create(self, autopsy: TradeAutopsy) -> LearningMemory:
        lessons = [
            "Keep deterministic calculations, risk approval, and execution authority independent from advisory memory",
            f"Review {autopsy.strategy_type.value} outcomes against the original thesis and recorded Hades objections",
        ]
        lessons.extend(f"Investigate: {item}" for item in autopsy.what_failed)
        lessons.extend(f"Reassess assumption: {item}" for item in autopsy.wrong_assumptions)
        return LearningMemory(
            id=str(uuid.uuid4()),
            source_run_id=autopsy.source_run_id,
            symbol=autopsy.symbol,
            lessons=lessons,
            confidence=0.85 if autopsy.execution_outcome == "FILLED" else 0.7,
        )
