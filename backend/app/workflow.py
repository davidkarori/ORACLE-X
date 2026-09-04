import asyncio
import hashlib
import json
import uuid
from datetime import date, timedelta
from typing import Any

from .config import Settings
from .domain import (
    AthenaDecision,
    CreateRunRequest,
    ExecutionValidation,
    GateResult,
    HadesDecision,
    LifecycleState,
    PositionState,
    RiskEvaluation,
    WorkflowRun,
    utc_now,
)
from .integrations import AlpacaClient, FeatherlessClient, IntegrationError
from .mcp_adapter import AlpacaMcpAdapter
from .post_trade import AutopsyService, LearningService
from .quant import QuantService, StrategyEngine, StrategyError, StrategyRequest, StressEngine
from .store import PersistenceStore


CANONICAL_PATH = [
    LifecycleState.DETECTED,
    LifecycleState.INVESTIGATING,
    LifecycleState.THESIS_CREATED,
    LifecycleState.THESIS_CHALLENGED,
    LifecycleState.STRATEGY_SELECTED,
    LifecycleState.STRESS_TESTED,
    LifecycleState.RISK_EVALUATED,
    LifecycleState.APPROVED,
    LifecycleState.EXECUTION_READY,
    LifecycleState.SUBMITTED,
    LifecycleState.FILLED,
    LifecycleState.POSITION_OPEN,
    LifecycleState.POSITION_MONITORING,
    LifecycleState.EXIT_SIGNAL,
    LifecycleState.EXIT_EXECUTION,
    LifecycleState.POSITION_CLOSED,
    LifecycleState.AUTOPSY,
    LifecycleState.LEARNED,
]
ALLOWED_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    state: {CANONICAL_PATH[index + 1], LifecycleState.REJECTED, LifecycleState.FAILED}
    for index, state in enumerate(CANONICAL_PATH[:-1])
}
ALLOWED_TRANSITIONS[LifecycleState.LEARNED] = set()
ALLOWED_TRANSITIONS[LifecycleState.REJECTED] = set()
ALLOWED_TRANSITIONS[LifecycleState.FAILED] = set()


class WorkflowService:
    def __init__(self, settings: Settings, store: PersistenceStore) -> None:
        self.settings = settings
        self.store = store
        self.featherless = FeatherlessClient(settings)
        self.alpaca = AlpacaClient(settings)
        self.mcp = AlpacaMcpAdapter(settings)
        self.strategy_engine = StrategyEngine()
        self.quant = QuantService()
        self.stress = StressEngine()
        self.autopsy_service = AutopsyService()
        self.learning_service = LearningService()
        if settings.kill_switch_active:
            self.set_kill_switch(True, "Initial configuration requested kill switch", actor="SYSTEM")
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def system_state(self):
        return self.store.get_system_state()

    @property
    def kill_switch(self) -> bool:
        return self.system_state.kill_switch_active

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
        configured = [self.settings.alpaca_configured, self.settings.featherless_configured, bool(self.settings.mcp_server_url)]
        mode = "connected" if all(configured) else "fixture" if not any(configured) else "mixed"
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            symbol=request.symbol,
            state=LifecycleState.DETECTED,
            status="RUNNING",
            mode=mode,
            execute_requested=request.execute,
            simulate_lifecycle=request.simulate_lifecycle,
            risk_profile=request.risk_profile,
            created_at=now,
            updated_at=now,
        )
        self.store.save_run(run)
        self.store.append(run.id, "OPPORTUNITY_DETECTED", "SYSTEM", {"symbol": run.symbol, "mode": mode})
        return run

    async def _run(self, run: WorkflowRun) -> None:
        try:
            self._transition(run, LifecycleState.INVESTIGATING, "SYSTEM", "Evidence collection started")
            run.market = await self.alpaca.market_context(run.symbol)
            self._event(run, "MARKET_EVIDENCE", "ALPACA_API", run.market.model_dump(mode="json"))

            run.mcp_calls, mcp_context = await self.mcp.research(run.symbol)
            for call in run.mcp_calls:
                self._event(run, "MCP_TOOL_CALL", call.requesting_agent.value, call.model_dump(mode="json"))
            if any(not call.success for call in run.mcp_calls):
                self._reject(run, "MCP_RESEARCH_FAILED")
                return

            memories = [memory.model_dump(mode="json") for memory in self.store.list_memories(run.symbol)]
            athena = await self.featherless.athena(
                {"symbol": run.symbol, "market": run.market.model_dump(mode="json"), "mcp": mcp_context, "advisory_memory": memories}
            )
            run.decisions.append(athena)
            self.store.save_agent_decision(run.id, athena)
            self._event(run, "AGENT_DECISION", "ATHENA", athena.model_dump(mode="json"))
            self._transition(run, LifecycleState.THESIS_CREATED, "ORCHESTRATOR", "Athena contract validated")

            athena, hades = await self._challenge(run, athena, mcp_context)
            if hades.recommendation == "REJECT":
                self._reject(run, "REJECTED_BY_HADES")
                return
            if hades.recommendation != "CONTINUE":
                self._reject(run, "HADES_REVISION_UNRESOLVED")
                return
            self._transition(run, LifecycleState.THESIS_CHALLENGED, "ORCHESTRATOR", "Hades objections resolved")

            hermes = await self.featherless.hermes(
                {
                    "symbol": run.symbol,
                    "athena": athena.model_dump(mode="json"),
                    "hades": hades.model_dump(mode="json"),
                    "market": run.market.model_dump(mode="json"),
                    "risk_profile": run.risk_profile,
                }
            )
            run.decisions.append(hermes)
            self.store.save_agent_decision(run.id, hermes)
            self._event(run, "AGENT_DECISION", "HERMES", hermes.model_dump(mode="json"))
            if hermes.directional_intent != athena.bias:
                raise StrategyError("Hermes directional intent conflicts with the surviving Athena thesis")
            request = StrategyRequest(
                bias=athena.bias,
                risk_profile=run.risk_profile,
                thesis=athena.thesis,
                recommended_family=hermes.preferred_strategy_family,
                target_risk_profile=hermes.target_risk_profile,
            )
            family = self.strategy_engine.select_family(request)
            legs = self.strategy_engine.build(run.market, request)
            run.strategy, run.quant = self.quant.evaluate(
                family,
                athena.thesis,
                athena.bias,
                legs,
                run.market.underlying_price,
                run.market.observed_at,
                self.settings.max_bid_ask_spread_pct,
            )
            self._event(run, "STRATEGY_SELECTION", "STRATEGY_ENGINE", run.strategy.model_dump(mode="json"))
            self._event(run, "QUANT_CALCULATION", "QUANT_SERVICE", run.quant.model_dump(mode="json"))
            self._transition(run, LifecycleState.STRATEGY_SELECTED, "ORCHESTRATOR", "Deterministic strategy normalized")

            run.stress = self.stress.evaluate(run.strategy, run.quant)
            self._event(run, "STRESS_TEST", "STRESS_ENGINE", run.stress.model_dump(mode="json"))
            morpheus = await self.featherless.morpheus(
                {
                    "symbol": run.symbol,
                    "athena": athena.model_dump(mode="json"),
                    "hades": hades.model_dump(mode="json"),
                    "strategy": run.strategy.model_dump(mode="json"),
                    "stress": run.stress.model_dump(mode="json"),
                }
            )
            run.decisions.append(morpheus)
            self.store.save_agent_decision(run.id, morpheus)
            self._event(run, "AGENT_DECISION", "MORPHEUS", morpheus.model_dump(mode="json"))
            self._transition(run, LifecycleState.STRESS_TESTED, "ORCHESTRATOR", "Deterministic stress evaluated and Morpheus verdict recorded")
            if run.stress.recommendation == "REJECT":
                self._reject(run, "REJECTED_BY_STRESS_ENGINE")
                return
            if morpheus.recommendation == "REJECT":
                self._reject(run, "REJECTED_BY_MORPHEUS")
                return

            run.risk = self._evaluate_risk(
                run,
                hades.recommendation,
                hermes.preferred_strategy_family.value,
                morpheus.recommendation,
            )
            self._event(run, "RISK_EVALUATION", "RISK_GOVERNOR", run.risk.model_dump(mode="json"))
            self.store.save_risk_evaluation(run.id, run.risk)
            self._transition(run, LifecycleState.RISK_EVALUATED, "RISK_GOVERNOR", "Hard gates evaluated")
            if run.risk.decision != "APPROVE":
                self._reject(run, *run.risk.reason_codes)
                return

            self._transition(run, LifecycleState.APPROVED, "RISK_GOVERNOR", "Every mandatory gate passed")
            self._transition(run, LifecycleState.EXECUTION_READY, "ORCHESTRATOR", "Approval is current and strategy is frozen")
            run.execution_guard = self._execution_guard(run)
            self._event(run, "EXECUTION_VALIDATION", "EXECUTION_GUARD", run.execution_guard.model_dump(mode="json"))
            if run.execution_guard.decision != "PASS":
                self._reject(run, *run.execution_guard.reason_codes)
                return

            if run.execute_requested:
                await self._submit(run)
                return
            if run.mode == "fixture" and run.simulate_lifecycle:
                await self._simulate_lifecycle(run)
                return
            run.status = "EXECUTION_READY"
            self._event(run, "DRY_RUN_COMPLETE", "EXECUTION_SERVICE", {"message": "No broker mutation requested"})
        except (IntegrationError, StrategyError) as exc:
            run.error = str(exc)
            run.status = "FAILED"
            self._fail(run, "CONTROLLED_FAILURE", str(exc))
        except Exception as exc:
            run.error = f"Unexpected workflow error: {exc}"
            run.status = "FAILED"
            self._fail(run, "WORKFLOW_FAILURE", run.error)
        finally:
            run.updated_at = utc_now()
            self.store.save_run(run)

    async def _challenge(
        self,
        run: WorkflowRun,
        athena: AthenaDecision,
        mcp_context: dict[str, Any],
    ) -> tuple[AthenaDecision, HadesDecision]:
        hades = await self.featherless.hades({"symbol": run.symbol, "athena": athena.model_dump(mode="json"), "mcp": mcp_context})
        run.decisions.append(hades)
        self.store.save_agent_decision(run.id, hades)
        self._event(run, "AGENT_DECISION", "HADES", hades.model_dump(mode="json"))
        if hades.recommendation != "REVISE":
            return athena, hades
        revised = await self.featherless.athena(
            {"symbol": run.symbol, "previous_thesis": athena.model_dump(mode="json"), "required_revision": hades.model_dump(mode="json")}
        )
        run.decisions.append(revised)
        self.store.save_agent_decision(run.id, revised)
        self._event(run, "THESIS_REVISION", "ATHENA", revised.model_dump(mode="json"))
        rereview = await self.featherless.hades(
            {"symbol": run.symbol, "athena": revised.model_dump(mode="json"), "previous_objections": hades.model_dump(mode="json")}
        )
        run.decisions.append(rereview)
        self.store.save_agent_decision(run.id, rereview)
        self._event(run, "AGENT_DECISION", "HADES", rereview.model_dump(mode="json"))
        return revised, rereview

    async def _submit(self, run: WorkflowRun) -> None:
        assert run.execution_guard and run.strategy and run.risk
        if run.mode == "connected":
            approved_strategy_hash = run.execution_guard.strategy_hash
            refreshed_market = await self.alpaca.market_context(run.symbol)
            run.market = refreshed_market
            if run.quant:
                run.quant.data_age_seconds = round(max(0.0, (utc_now() - refreshed_market.observed_at).total_seconds()), 3)
            self._event(run, "FINAL_MARKET_REFRESH", "EXECUTION_GUARD", refreshed_market.model_dump(mode="json"))
            run.execution_guard = self._execution_guard(run)
            if run.execution_guard.strategy_hash != approved_strategy_hash:
                run.execution_guard.decision = "BLOCK"
                run.execution_guard.reason_codes.append("APPROVED_STRATEGY_HASH_CHANGED")
            self._event(run, "FINAL_EXECUTION_VALIDATION", "EXECUTION_GUARD", run.execution_guard.model_dump(mode="json"))
            if run.execution_guard.decision != "PASS":
                self._reject(run, *run.execution_guard.reason_codes)
                return
        fingerprint = self._execution_fingerprint(run)
        if self.store.has_active_execution_conflict(fingerprint):
            self._reject(run, "DUPLICATE_ECONOMIC_INTENT")
            return
        if not self.store.reserve_execution_intent(run.execution_guard.idempotency_key, run.id, fingerprint):
            self._reject(run, "DUPLICATE_ORDER_INTENT")
            return
        run.broker_order = await self.alpaca.submit_strategy(run.strategy, run.execution_guard.idempotency_key)
        self.store.save_broker_order(run.id, run.broker_order)
        self.store.save_reconciliation_event(run.id, run.broker_order.get("reconciliation_status", "UNKNOWN"), {"order": run.broker_order})
        self._event(run, "BROKER_ORDER", "EXECUTION_SERVICE", run.broker_order)
        if run.broker_order.get("reconciliation_status") != "KNOWN":
            self._reject(run, "BROKER_RECONCILIATION_UNKNOWN")
            return
        self._transition(run, LifecycleState.SUBMITTED, "EXECUTION_SERVICE", "Alpaca accepted paper order")
        run.status = "SUBMITTED"

    async def _simulate_lifecycle(self, run: WorkflowRun) -> None:
        assert run.strategy and run.quant
        run.broker_order = {
            "broker": "fixture",
            "order_id": f"sim-{run.id[:8]}",
            "client_order_id": run.execution_guard.idempotency_key if run.execution_guard else None,
            "status": "filled",
            "request_payload": {},
            "raw_response": {},
            "legs": [],
            "fills": [],
            "positions": [],
            "reconciliation_status": "SIMULATED",
            "reconciliation_events": [],
            "simulated": True,
        }
        self._event(run, "SIMULATION_STARTED", "FIXTURE_SIMULATOR", {"broker_mutation": False})
        self._transition(run, LifecycleState.SUBMITTED, "FIXTURE_SIMULATOR", "Simulated order accepted; no broker called")
        self._transition(run, LifecycleState.FILLED, "FIXTURE_SIMULATOR", "Simulated fill recorded")
        now = utc_now()
        run.position = PositionState(
            status="OPEN",
            quantity=run.strategy.quantity,
            entry_value=run.strategy.net_debit or run.strategy.max_loss,
            current_value=run.strategy.net_debit or run.strategy.max_loss,
            opened_at=now,
            simulated=True,
        )
        self._event(run, "POSITION_SNAPSHOT", "POSITION_SERVICE", run.position.model_dump(mode="json"))
        self._transition(run, LifecycleState.POSITION_OPEN, "POSITION_SERVICE", "Simulated position opened")
        run.position.status = "MONITORING"
        simulated_pnl = round(min(run.strategy.max_profit or run.strategy.max_loss, run.strategy.max_loss * 0.18), 2)
        run.position.current_value = round(run.position.entry_value + simulated_pnl, 2)
        run.position.unrealized_pnl = simulated_pnl
        self._transition(run, LifecycleState.POSITION_MONITORING, "POSITION_SERVICE", "Single deterministic fixture snapshot evaluated")
        self._event(run, "POSITION_SNAPSHOT", "POSITION_SERVICE", run.position.model_dump(mode="json"))
        self._transition(run, LifecycleState.EXIT_SIGNAL, "EXIT_POLICY", "Fixture profit target reached")
        self._transition(run, LifecycleState.EXIT_EXECUTION, "EXECUTION_SERVICE", "Simulated close intent validated; no broker called")
        run.position.status = "CLOSED"
        run.position.realized_pnl = simulated_pnl
        run.position.unrealized_pnl = 0
        run.position.closed_at = utc_now()
        self._transition(run, LifecycleState.POSITION_CLOSED, "POSITION_SERVICE", "Simulated position closed")
        self._event(run, "POSITION_CLOSED", "POSITION_SERVICE", run.position.model_dump(mode="json"))
        self._transition(run, LifecycleState.AUTOPSY, "ORCHESTRATOR", "Immutable trade record ready for autopsy")
        run.autopsy = self.autopsy_service.create(run)
        self._event(run, "TRADE_AUTOPSY", "AUTOPSY_SERVICE", run.autopsy.model_dump(mode="json"))
        run.memory = self.learning_service.create(run.autopsy)
        self.store.save_memory(run.memory)
        self._event(run, "LEARNING_MEMORY", "LEARNING_SERVICE", run.memory.model_dump(mode="json"))
        self._transition(run, LifecycleState.LEARNED, "ORCHESTRATOR", "Advisory-only memory stored")
        run.status = "LEARNED"

    def _evaluate_risk(
        self,
        run: WorkflowRun,
        hades_recommendation: str,
        hermes_family: str,
        morpheus_recommendation: str,
    ) -> RiskEvaluation:
        assert run.market and run.quant and run.strategy and run.stress
        now = utc_now()
        system_state = self.store.get_system_state()
        days_to_expiration = (date.fromisoformat(run.strategy.expiration) - now.date()).days
        reward_risk_ok = run.quant.reward_risk is None or run.quant.reward_risk >= self.settings.min_reward_risk
        gates = [
            GateResult(code="PAPER_MODE", passed=self.settings.trading_mode == "paper", measured=self.settings.trading_mode, limit="paper"),
            GateResult(code="SYSTEM_ACTIVE", passed=system_state.status == "ACTIVE", measured=system_state.status, limit="ACTIVE"),
            GateResult(code="KILL_SWITCH", passed=not system_state.kill_switch_active, measured=system_state.kill_switch_active, limit=False),
            GateResult(code="ACCOUNT_ACTIVE", passed="ACTIVE" in run.market.account_status, measured=run.market.account_status, limit="ACTIVE"),
            GateResult(code="OPTIONS_APPROVAL", passed=run.market.options_approved_level >= self.settings.alpaca_min_options_level, measured=run.market.options_approved_level, limit=self.settings.alpaca_min_options_level),
            GateResult(code="HADES_CONTINUE", passed=hades_recommendation == "CONTINUE", measured=hades_recommendation, limit="CONTINUE"),
            GateResult(code="HERMES_FAMILY_VALIDATED", passed=run.strategy.strategy_type.value == hermes_family, measured=hermes_family, limit=run.strategy.strategy_type.value),
            GateResult(code="STRESS_ACCEPTABLE", passed=run.stress.recommendation != "REJECT", measured=run.stress.recommendation, limit="PASS or CAUTION"),
            GateResult(code="MORPHEUS_NOT_REJECTED", passed=morpheus_recommendation != "REJECT", measured=morpheus_recommendation, limit="PASS or CAUTION"),
            GateResult(code="DATA_FRESH", passed=run.quant.data_age_seconds <= self.settings.max_market_data_age_seconds, measured=run.quant.data_age_seconds, limit=self.settings.max_market_data_age_seconds),
            GateResult(code="MAX_TRADE_LOSS", passed=run.quant.max_loss <= self.settings.max_trade_loss, measured=run.quant.max_loss, limit=self.settings.max_trade_loss),
            GateResult(code="PORTFOLIO_EXPOSURE", passed=run.market.portfolio_exposure + run.quant.exposure <= self.settings.max_portfolio_exposure, measured=run.market.portfolio_exposure + run.quant.exposure, limit=self.settings.max_portfolio_exposure),
            GateResult(code="SYMBOL_CONCENTRATION", passed=run.market.symbol_exposure + run.quant.exposure <= self.settings.max_symbol_exposure, measured=run.market.symbol_exposure + run.quant.exposure, limit=self.settings.max_symbol_exposure),
            GateResult(code="MAX_OPEN_TRADES", passed=run.market.open_trade_count < self.settings.max_open_trades, measured=run.market.open_trade_count, limit=self.settings.max_open_trades),
            GateResult(code="MIN_REWARD_RISK", passed=reward_risk_ok, measured=run.quant.reward_risk, limit=self.settings.min_reward_risk),
            GateResult(code="EXPIRATION_WINDOW", passed=self.settings.min_days_to_expiration <= days_to_expiration <= self.settings.max_days_to_expiration, measured=days_to_expiration, limit=[self.settings.min_days_to_expiration, self.settings.max_days_to_expiration]),
            GateResult(code="LIQUIDITY", passed=run.quant.liquidity_passed, measured=run.quant.max_spread_pct, limit=self.settings.max_bid_ask_spread_pct),
            GateResult(code="QUANTITY", passed=run.quant.position_quantity <= self.settings.max_position_quantity, measured=run.quant.position_quantity, limit=self.settings.max_position_quantity),
            GateResult(code="BUYING_POWER", passed=run.quant.exposure <= run.market.buying_power, measured=run.quant.exposure, limit=run.market.buying_power),
            GateResult(code="BROKER_HEALTH", passed=run.market.account_status in {"ACTIVE", "FIXTURE_ACTIVE"}, measured=run.market.account_status, limit="ACTIVE"),
            GateResult(code="POSITION_RECONCILED", passed=not run.market.conflicting_orders and not run.market.conflicting_positions, measured={"orders": run.market.conflicting_orders, "positions": run.market.conflicting_positions}, limit="no conflicting orders or positions"),
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
        assert run.risk and run.market and run.strategy and run.quant
        strategy_hash = uuid.uuid5(uuid.NAMESPACE_URL, run.strategy.model_dump_json()).hex
        idempotency_key = f"oracle-x-{self._execution_fingerprint(run)[:24]}"
        system_state = self.store.get_system_state()
        days_to_expiration = (date.fromisoformat(run.strategy.expiration) - utc_now().date()).days
        structure_valid = True
        try:
            self.strategy_engine.validate(run.strategy.strategy_type, run.strategy.legs)
        except StrategyError:
            structure_valid = False
        checks = [
            GateResult(code="EXECUTION_READY", passed=run.state == LifecycleState.EXECUTION_READY, measured=run.state.value, limit="EXECUTION_READY"),
            GateResult(code="APPROVAL_VALID", passed=run.risk.expires_at > utc_now(), measured=run.risk.expires_at.isoformat(), limit="future"),
            GateResult(code="RISK_APPROVED", passed=run.risk.decision == "APPROVE", measured=run.risk.decision, limit="APPROVE"),
            GateResult(code="STRATEGY_VALID", passed=structure_valid, measured=run.strategy.strategy_type.value, limit="normalized defined risk"),
            GateResult(code="QUANT_MATCH", passed=run.strategy.max_loss == run.quant.max_loss, measured=run.strategy.max_loss, limit=run.quant.max_loss),
            GateResult(code="SYSTEM_ACTIVE", passed=system_state.status == "ACTIVE", measured=system_state.status, limit="ACTIVE"),
            GateResult(code="KILL_SWITCH", passed=not system_state.kill_switch_active, measured=system_state.kill_switch_active, limit=False),
            GateResult(code="PAPER_ENDPOINT", passed=self.settings.is_paper_endpoint, measured=self.settings.alpaca_trading_base_url, limit="https://paper-api.alpaca.markets"),
            GateResult(code="DATA_ENDPOINT", passed=self.settings.is_data_endpoint, measured=self.settings.alpaca_data_base_url, limit="https://data.alpaca.markets"),
            GateResult(code="LIVE_EVIDENCE_FOR_MUTATION", passed=(not run.execute_requested or run.market.source == "alpaca"), measured=run.market.source, limit="alpaca when executing"),
            GateResult(code="LIVE_INFERENCE_FOR_MUTATION", passed=(not run.execute_requested or all(decision.provider == "featherless" for decision in run.decisions)), measured=sorted({decision.provider for decision in run.decisions}), limit="featherless when executing"),
            GateResult(code="MCP_RESEARCH_FOR_MUTATION", passed=(not run.execute_requested or bool(self.settings.mcp_server_url) and all(call.success for call in run.mcp_calls)), measured={"configured": bool(self.settings.mcp_server_url), "successful_calls": sum(call.success for call in run.mcp_calls)}, limit="configured with all research calls successful when executing"),
            GateResult(code="EXECUTION_ENABLED", passed=(not run.execute_requested or self.settings.execution_enabled), measured=self.settings.execution_enabled, limit=True if run.execute_requested else "not required"),
            GateResult(code="ACCOUNT_ACTIVE", passed="ACTIVE" in run.market.account_status, measured=run.market.account_status, limit="ACTIVE"),
            GateResult(code="OPTIONS_APPROVAL", passed=run.market.options_approved_level >= self.settings.alpaca_min_options_level, measured=run.market.options_approved_level, limit=self.settings.alpaca_min_options_level),
            GateResult(code="MARKET_SESSION", passed=run.market.market_is_open, measured=run.market.market_is_open, limit=True),
            GateResult(code="CONTRACTS_ACTIVE", passed=all(leg.expiration >= utc_now().date().isoformat() for leg in run.strategy.legs), measured=[leg.expiration for leg in run.strategy.legs], limit="not expired"),
            GateResult(code="EXPIRATION_WINDOW", passed=self.settings.min_days_to_expiration <= days_to_expiration <= self.settings.max_days_to_expiration, measured=days_to_expiration, limit=[self.settings.min_days_to_expiration, self.settings.max_days_to_expiration]),
            GateResult(code="NO_CONFLICTING_BROKER_STATE", passed=not run.market.conflicting_orders and not run.market.conflicting_positions, measured={"orders": run.market.conflicting_orders, "positions": run.market.conflicting_positions}, limit="none"),
        ]
        reasons = [check.code for check in checks if not check.passed]
        return ExecutionValidation(
            decision="PASS" if not reasons else "BLOCK",
            reason_codes=reasons,
            checks=checks,
            idempotency_key=idempotency_key,
            strategy_hash=strategy_hash,
            validated_at=utc_now(),
        )

    def set_kill_switch(self, active: bool, reason: str, actor: str = "OPERATOR") -> bool:
        from .domain import SystemState

        state = SystemState(status="HALTED" if active else "ACTIVE", kill_switch_active=active, changed_by=actor, reason=reason, updated_at=utc_now())
        self.store.set_system_state(state)
        return state.kill_switch_active

    def _execution_fingerprint(self, run: WorkflowRun) -> str:
        assert run.risk and run.strategy
        immutable = {
            "account": "alpaca-paper",
            "symbol": run.symbol,
            "strategy_family": run.strategy.strategy_type.value,
            "expiration": run.strategy.expiration,
            "legs": [
                {
                    "symbol": leg.contract_symbol,
                    "strike": leg.strike,
                    "type": leg.option_type,
                    "side": leg.side,
                    "quantity": leg.quantity,
                    "ratio": leg.ratio,
                    "intent": leg.position_intent,
                }
                for leg in run.strategy.legs
            ],
            "price_intent": {"net_debit": run.strategy.net_debit, "net_credit": run.strategy.net_credit},
            "risk_policy": run.risk.policy_version,
            "risk_decision": run.risk.decision,
            "approved_max_loss": run.strategy.max_loss,
        }
        return hashlib.sha256(json.dumps(immutable, sort_keys=True).encode()).hexdigest()

    def _transition(self, run: WorkflowRun, new_state: LifecycleState, actor: str, reason: str) -> None:
        if new_state not in ALLOWED_TRANSITIONS.get(run.state, set()):
            self._event(run, "STATE_TRANSITION_REJECTED", actor, {"from": run.state.value, "to": new_state.value, "reason": reason})
            raise RuntimeError(f"Invalid transition {run.state.value} -> {new_state.value}")
        previous = run.state
        run.state = new_state
        run.updated_at = utc_now()
        self._event(run, "STATE_TRANSITION", actor, {"from": previous.value, "to": new_state.value, "reason": reason})
        self.store.save_run(run)

    def _reject(self, run: WorkflowRun, *reason_codes: str) -> None:
        reason = ", ".join(reason_codes) or "REJECTED"
        self._transition(run, LifecycleState.REJECTED, "ORCHESTRATOR", reason)
        run.status = "REJECTED"
        self._event(run, "WORKFLOW_REJECTED", "ORCHESTRATOR", {"reason_codes": list(reason_codes)})

    def _fail(self, run: WorkflowRun, code: str, reason: str) -> None:
        if LifecycleState.FAILED in ALLOWED_TRANSITIONS.get(run.state, set()):
            self._transition(run, LifecycleState.FAILED, "SYSTEM", reason)
        self._event(run, code, "SYSTEM", {"reason": reason})

    def _event(self, run: WorkflowRun, kind: str, actor: str, payload: dict[str, Any]) -> None:
        self.store.append(run.id, kind, actor, payload)
