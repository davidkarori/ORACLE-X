import asyncio
import uuid
from datetime import timedelta
from typing import Any

from .config import Settings
from .domain import (
    AgentRole,
    CreateRunRequest,
    ExecutionValidation,
    GateResult,
    LifecycleState,
    OptionLeg,
    QuantMetrics,
    RiskEvaluation,
    Strategy,
    WorkflowRun,
    utc_now,
)
from .integrations import AlpacaClient, FeatherlessClient, IntegrationError
from .store import AuditStore


ALLOWED_TRANSITIONS = {
    LifecycleState.DETECTED: {LifecycleState.INVESTIGATING, LifecycleState.FAILED},
    LifecycleState.INVESTIGATING: {LifecycleState.THESIS_CREATED, LifecycleState.FAILED},
    LifecycleState.THESIS_CREATED: {LifecycleState.THESIS_CHALLENGED, LifecycleState.REJECTED, LifecycleState.FAILED},
    LifecycleState.THESIS_CHALLENGED: {LifecycleState.STRATEGY_SELECTED, LifecycleState.REJECTED, LifecycleState.FAILED},
    LifecycleState.STRATEGY_SELECTED: {LifecycleState.STRESS_TESTED, LifecycleState.FAILED},
    LifecycleState.STRESS_TESTED: {LifecycleState.RISK_EVALUATED, LifecycleState.FAILED},
    LifecycleState.RISK_EVALUATED: {LifecycleState.APPROVED, LifecycleState.REJECTED, LifecycleState.FAILED},
    LifecycleState.APPROVED: {LifecycleState.EXECUTION_READY, LifecycleState.REJECTED},
    LifecycleState.EXECUTION_READY: {LifecycleState.SUBMITTED, LifecycleState.REJECTED, LifecycleState.FAILED},
}


class WorkflowService:
    def __init__(self, settings: Settings, store: AuditStore) -> None:
        self.settings = settings
        self.store = store
        self.featherless = FeatherlessClient(settings)
        self.alpaca = AlpacaClient(settings)
        self.kill_switch = settings.kill_switch_active
        self._tasks: set[asyncio.Task[Any]] = set()

    def start(self, request: CreateRunRequest) -> WorkflowRun:
        run = self._create_run(request)
        task = asyncio.create_task(self._run(run))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run

    async def run_to_completion(self, request: CreateRunRequest) -> WorkflowRun:
        run = self._create_run(request)
        await self._run(run)
        return run

    def _create_run(self, request: CreateRunRequest) -> WorkflowRun:
        now = utc_now()
        run = WorkflowRun(
            id=uuid.uuid4().hex,
            symbol=request.symbol,
            state=LifecycleState.DETECTED,
            status="RUNNING",
            mode="live-integrations" if self.settings.alpaca_configured else "fixture",
            execute_requested=request.execute,
            created_at=now,
            updated_at=now,
        )
        self.store.save_run(run)
        self.store.append(run.id, "OPPORTUNITY_DETECTED", "SYSTEM", {"symbol": run.symbol})
        return run

    async def _run(self, run: WorkflowRun) -> None:
        try:
            self._transition(run, LifecycleState.INVESTIGATING, "SYSTEM", "Evidence collection started")
            run.market = await self.alpaca.market_context(run.symbol)
            self._event(run, "MARKET_EVIDENCE", "ALPACA", run.market.model_dump(mode="json"))

            athena = await self.featherless.decide(
                AgentRole.ATHENA, {"symbol": run.symbol, "market": run.market.model_dump(mode="json")}
            )
            run.decisions.append(athena)
            self._event(run, "AGENT_DECISION", "ATHENA", athena.model_dump(mode="json"))
            self._transition(run, LifecycleState.THESIS_CREATED, "ORCHESTRATOR", "Athena contract validated")

            hades = await self.featherless.decide(
                AgentRole.HADES, {"symbol": run.symbol, "athena": athena.model_dump(mode="json")}
            )
            run.decisions.append(hades)
            self._event(run, "AGENT_DECISION", "HADES", hades.model_dump(mode="json"))
            self._transition(run, LifecycleState.THESIS_CHALLENGED, "ORCHESTRATOR", "Hades critique recorded")

            hermes = await self.featherless.decide(
                AgentRole.HERMES,
                {"symbol": run.symbol, "market": run.market.model_dump(mode="json"), "critique": hades.model_dump(mode="json")},
            )
            run.decisions.append(hermes)
            run.strategy, run.quant = self._build_strategy(run, athena.summary)
            self._event(run, "AGENT_DECISION", "HERMES", hermes.model_dump(mode="json"))
            self._event(run, "QUANT_CALCULATION", "QUANT_SERVICE", run.quant.model_dump(mode="json"))
            self._transition(run, LifecycleState.STRATEGY_SELECTED, "ORCHESTRATOR", "Strategy normalized")

            morpheus = await self.featherless.decide(
                AgentRole.MORPHEUS,
                {"symbol": run.symbol, "strategy": run.strategy.model_dump(mode="json"), "quant": run.quant.model_dump(mode="json")},
            )
            run.decisions.append(morpheus)
            self._event(run, "AGENT_DECISION", "MORPHEUS", morpheus.model_dump(mode="json"))
            self._transition(run, LifecycleState.STRESS_TESTED, "ORCHESTRATOR", "Morpheus stress assessment recorded")

            run.risk = self._evaluate_risk(run)
            self._event(run, "RISK_EVALUATION", "RISK_GOVERNOR", run.risk.model_dump(mode="json"))
            self._transition(run, LifecycleState.RISK_EVALUATED, "RISK_GOVERNOR", "Hard gates evaluated")
            if run.risk.decision != "APPROVE":
                self._transition(run, LifecycleState.REJECTED, "RISK_GOVERNOR", ", ".join(run.risk.reason_codes))
                run.status = "REJECTED"
                return

            self._transition(run, LifecycleState.APPROVED, "RISK_GOVERNOR", "Every mandatory gate passed")
            self._transition(run, LifecycleState.EXECUTION_READY, "ORCHESTRATOR", "Approval is current and strategy is frozen")
            run.execution_guard = self._execution_guard(run)
            self._event(run, "EXECUTION_VALIDATION", "EXECUTION_GUARD", run.execution_guard.model_dump(mode="json"))
            if run.execution_guard.decision != "PASS":
                self._transition(run, LifecycleState.REJECTED, "EXECUTION_GUARD", ", ".join(run.execution_guard.reason_codes))
                run.status = "REJECTED"
                return

            if not run.execute_requested:
                run.status = "EXECUTION_READY"
                self._event(run, "DRY_RUN_COMPLETE", "EXECUTION_SERVICE", {"message": "No broker mutation requested"})
                return

            leg = run.strategy.legs[0]
            if not self.store.reserve_execution(run.execution_guard.idempotency_key, run.id):
                self._transition(run, LifecycleState.REJECTED, "EXECUTION_GUARD", "DUPLICATE_ORDER_INTENT")
                run.status = "REJECTED"
                return
            run.broker_order = await self.alpaca.submit(
                leg.contract_symbol, leg.quantity, leg.limit_price, run.execution_guard.idempotency_key
            )
            self._event(run, "BROKER_ORDER", "EXECUTION_SERVICE", run.broker_order)
            self._transition(run, LifecycleState.SUBMITTED, "EXECUTION_SERVICE", "Alpaca accepted paper order")
            run.status = "SUBMITTED"
        except IntegrationError as exc:
            run.error = str(exc)
            run.status = "FAILED"
            self._fail(run, "DEPENDENCY_FAILURE", str(exc))
        except Exception as exc:
            run.error = f"Unexpected workflow error: {exc}"
            run.status = "FAILED"
            self._fail(run, "WORKFLOW_FAILURE", run.error)
        finally:
            run.updated_at = utc_now()
            self.store.save_run(run)

    def _build_strategy(self, run: WorkflowRun, thesis: str) -> tuple[Strategy, QuantMetrics]:
        assert run.market is not None
        midpoint = round((run.market.bid + run.market.ask) / 2, 2)
        spread_pct = round((run.market.ask - run.market.bid) / midpoint * 100, 2)
        quantity = 1
        premium = round(run.market.ask * 100 * quantity, 2)
        data_age = max(0.0, (utc_now() - run.market.observed_at).total_seconds())
        leg = OptionLeg(
            contract_symbol=run.market.option_symbol,
            underlying_symbol=run.symbol,
            option_type="CALL",
            expiration=run.market.expiration,
            strike=run.market.strike,
            side="BUY",
            quantity=quantity,
            ratio=1,
            position_intent="OPEN",
            limit_price=midpoint,
        )
        strategy = Strategy(
            thesis=thesis,
            legs=[leg],
            net_debit=premium,
            max_loss=premium,
            break_even=[round(run.market.strike + midpoint, 2)],
        )
        quant = QuantMetrics(
            midpoint=midpoint,
            spread_pct=spread_pct,
            premium=premium,
            max_loss=premium,
            position_quantity=quantity,
            data_age_seconds=round(data_age, 3),
        )
        return strategy, quant

    def _evaluate_risk(self, run: WorkflowRun) -> RiskEvaluation:
        assert run.market and run.quant and run.strategy
        now = utc_now()
        gates = [
            GateResult(code="PAPER_MODE", passed=self.settings.trading_mode == "paper", measured=self.settings.trading_mode, limit="paper"),
            GateResult(code="KILL_SWITCH", passed=not self.kill_switch, measured=self.kill_switch, limit=False),
            GateResult(code="ACCOUNT_ACTIVE", passed="ACTIVE" in run.market.account_status, measured=run.market.account_status, limit="ACTIVE"),
            GateResult(code="DATA_FRESH", passed=run.quant.data_age_seconds <= self.settings.max_market_data_age_seconds, measured=run.quant.data_age_seconds, limit=self.settings.max_market_data_age_seconds),
            GateResult(code="MAX_TRADE_LOSS", passed=run.quant.max_loss <= self.settings.max_trade_loss, measured=run.quant.max_loss, limit=self.settings.max_trade_loss),
            GateResult(code="SPREAD", passed=run.quant.spread_pct <= self.settings.max_bid_ask_spread_pct, measured=run.quant.spread_pct, limit=self.settings.max_bid_ask_spread_pct),
            GateResult(code="QUANTITY", passed=run.quant.position_quantity <= self.settings.max_position_quantity, measured=run.quant.position_quantity, limit=self.settings.max_position_quantity),
            GateResult(code="BUYING_POWER", passed=run.quant.max_loss <= run.market.buying_power, measured=run.quant.max_loss, limit=run.market.buying_power),
        ]
        reasons = [gate.code for gate in gates if not gate.passed]
        return RiskEvaluation(
            decision="APPROVE" if not reasons else "REJECT",
            reason_codes=reasons,
            gates=gates,
            evaluated_at=now,
            expires_at=now + timedelta(seconds=self.settings.risk_approval_ttl_seconds),
        )

    def _execution_guard(self, run: WorkflowRun) -> ExecutionValidation:
        assert run.risk and run.market and run.strategy
        frozen_hash = uuid.uuid5(uuid.NAMESPACE_URL, run.strategy.model_dump_json()).hex[:20]
        idempotency_key = f"oracle-x-{run.id[:12]}-{frozen_hash[:8]}"
        checks = [
            GateResult(code="EXECUTION_READY", passed=run.state == LifecycleState.EXECUTION_READY, measured=run.state.value, limit="EXECUTION_READY"),
            GateResult(code="APPROVAL_VALID", passed=run.risk.expires_at > utc_now(), measured=run.risk.expires_at.isoformat(), limit="future"),
            GateResult(code="RISK_APPROVED", passed=run.risk.decision == "APPROVE", measured=run.risk.decision, limit="APPROVE"),
            GateResult(code="KILL_SWITCH", passed=not self.kill_switch, measured=self.kill_switch, limit=False),
            GateResult(code="PAPER_ENDPOINT", passed=self.settings.is_paper_endpoint, measured=self.settings.alpaca_trading_base_url, limit="https://paper-api.alpaca.markets"),
            GateResult(code="LIVE_EVIDENCE_FOR_MUTATION", passed=(not run.execute_requested or run.market.source == "alpaca"), measured=run.market.source, limit="alpaca when executing"),
            GateResult(code="LIVE_INFERENCE_FOR_MUTATION", passed=(not run.execute_requested or all(decision.provider == "featherless" for decision in run.decisions)), measured=sorted({decision.provider for decision in run.decisions}), limit="featherless when executing"),
            GateResult(code="EXECUTION_ENABLED", passed=(not run.execute_requested or self.settings.execution_enabled), measured=self.settings.execution_enabled, limit=True if run.execute_requested else "not required"),
        ]
        reasons = [check.code for check in checks if not check.passed]
        return ExecutionValidation(
            decision="PASS" if not reasons else "BLOCK",
            reason_codes=reasons,
            checks=checks,
            idempotency_key=idempotency_key,
            validated_at=utc_now(),
        )

    def _transition(self, run: WorkflowRun, new_state: LifecycleState, actor: str, reason: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(run.state, set())
        if new_state not in allowed:
            self._event(run, "STATE_TRANSITION_REJECTED", actor, {"from": run.state.value, "to": new_state.value, "reason": reason})
            raise RuntimeError(f"Invalid transition {run.state.value} -> {new_state.value}")
        previous = run.state
        run.state = new_state
        run.updated_at = utc_now()
        self._event(run, "STATE_TRANSITION", actor, {"from": previous.value, "to": new_state.value, "reason": reason})
        self.store.save_run(run)

    def _fail(self, run: WorkflowRun, code: str, reason: str) -> None:
        if LifecycleState.FAILED in ALLOWED_TRANSITIONS.get(run.state, set()):
            self._transition(run, LifecycleState.FAILED, "SYSTEM", reason)
        self._event(run, code, "SYSTEM", {"reason": reason})

    def _event(self, run: WorkflowRun, kind: str, actor: str, payload: dict[str, Any]) -> None:
        self.store.append(run.id, kind, actor, payload)
