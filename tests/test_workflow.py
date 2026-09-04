import asyncio
import sqlite3
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.domain import (
    AgentRole,
    Bias,
    CreateRunRequest,
    HadesDecision,
    HermesDecision,
    LearningMemory,
    LifecycleState,
    MorpheusDecision,
    OptionLeg,
    StrategyFamily,
    WorkflowRun,
    utc_now,
)
from app.integrations import AlpacaClient, FeatherlessClient, IntegrationError
from app.mcp_adapter import AlpacaMcpAdapter
from app.quant import QuantService, StrategyEngine, StrategyError, StrategyRequest, StressEngine
from app.store import AuditStore, build_store
from app.workflow import WorkflowService


async def wait_for_run(store: AuditStore, run_id: str):
    for _ in range(200):
        run = store.get_run(run_id)
        if run and run.status != "RUNNING":
            return run
        await asyncio.sleep(0.01)
    raise AssertionError("workflow did not finish")


def service_for(path: str = ":memory:", **overrides) -> WorkflowService:
    settings = Settings(oracle_db_path=path, **overrides)
    return WorkflowService(settings, AuditStore(path))


def run_record(run_id: str = "00000000-0000-0000-0000-000000000001") -> WorkflowRun:
    now = utc_now()
    return WorkflowRun(
        id=run_id,
        symbol="SPY",
        state=LifecycleState.DETECTED,
        status="RUNNING",
        mode="fixture",
        execute_requested=False,
        simulate_lifecycle=False,
        risk_profile="CONSERVATIVE",
        created_at=now,
        updated_at=now,
    )


def strategy_request(bias: Bias, profile: str, family: StrategyFamily) -> StrategyRequest:
    target = "PREMIUM_ONLY" if family in {StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT} else "DEFINED_RISK"
    return StrategyRequest(
        bias=bias,
        risk_profile=profile,
        thesis="A sufficiently detailed deterministic test thesis.",
        recommended_family=family,
        target_risk_profile=target,
    )


@pytest.mark.asyncio
async def test_fixture_flow_reaches_execution_ready_without_broker_mutation():
    service = service_for()
    run = await service.run_to_completion(CreateRunRequest(symbol="SPY", simulate_lifecycle=False))

    assert run.state == LifecycleState.EXECUTION_READY
    assert run.status == "EXECUTION_READY"
    assert run.strategy and run.strategy.strategy_type == StrategyFamily.BULL_CALL_SPREAD
    assert run.broker_order is None
    assert run.risk and run.risk.decision == "APPROVE"
    assert run.execution_guard and run.execution_guard.decision == "PASS"


@pytest.mark.asyncio
async def test_hades_can_reject_a_weak_thesis():
    service = service_for()
    rejection = service.featherless._fixture(AgentRole.HADES, {"symbol": "SPY"}, HadesDecision).model_copy(
        update={"fatal_objections": ["No supporting evidence"], "recommendation": "REJECT"}
    )

    async def reject(_context):
        return rejection

    service.featherless.hades = reject
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=False))

    assert run.state == LifecycleState.REJECTED
    assert run.risk is None
    assert any(event.kind == "WORKFLOW_REJECTED" for event in service.store.events(run.id))


@pytest.mark.asyncio
async def test_hades_cannot_authorize_execution():
    service = service_for(execution_enabled=True)
    run = await service.run_to_completion(CreateRunRequest(execute=True, simulate_lifecycle=False))

    assert run.state == LifecycleState.REJECTED
    assert "LIVE_EVIDENCE_FOR_MUTATION" in run.execution_guard.reason_codes
    assert "LIVE_INFERENCE_FOR_MUTATION" in run.execution_guard.reason_codes
    assert run.broker_order is None


@pytest.mark.asyncio
async def test_hermes_strategy_recommendation_affects_family_selection():
    service = service_for()
    recommendation = service.featherless._fixture(
        AgentRole.HERMES,
        {"symbol": "SPY", "athena": {"bias": "BULLISH"}, "risk_profile": "AGGRESSIVE"},
        HermesDecision,
    ).model_copy(
        update={"preferred_strategy_family": StrategyFamily.BULL_CALL_SPREAD, "target_risk_profile": "DEFINED_RISK"}
    )

    async def recommend(_context):
        return recommendation

    service.featherless.hermes = recommend
    run = await service.run_to_completion(CreateRunRequest(risk_profile="AGGRESSIVE", simulate_lifecycle=False))

    assert run.strategy and run.strategy.strategy_type == StrategyFamily.BULL_CALL_SPREAD
    assert len(run.strategy.legs) == 2


def test_hermes_contract_cannot_carry_authoritative_numbers():
    client = FeatherlessClient(Settings())
    payload = {
        "confidence": 0.8,
        "evidence_refs": ["market"],
        "preferred_strategy_family": "BULL_CALL_SPREAD",
        "rationale": "A bounded bullish spread matches the surviving thesis.",
        "directional_intent": "BULLISH",
        "target_risk_profile": "DEFINED_RISK",
        "structural_intent": ["Buy lower call and sell higher call"],
        "max_loss": 123.45,
    }

    with pytest.raises(IntegrationError, match="Malformed HERMES"):
        client.parse_for_test(AgentRole.HERMES, payload)


@pytest.mark.asyncio
async def test_morpheus_can_reject_before_risk_governor():
    service = service_for()
    rejection = service.featherless._fixture(
        AgentRole.MORPHEUS,
        {"symbol": "SPY", "stress": {"recommendation": "CAUTION", "scenarios": []}},
        MorpheusDecision,
    ).model_copy(update={"recommendation": "REJECT"})

    async def reject(_context):
        return rejection

    service.featherless.morpheus = reject
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=False))

    assert run.state == LifecycleState.REJECTED
    assert run.risk is None
    assert any(
        event.payload.get("reason_codes") == ["REJECTED_BY_MORPHEUS"]
        for event in service.store.events(run.id)
        if event.kind == "WORKFLOW_REJECTED"
    )


def test_strategy_engine_rejects_naked_short_structure():
    quote = AlpacaClient._fixture("SPY").option_chain[0]
    naked = OptionLeg(
        contract_symbol=quote.contract_symbol,
        underlying_symbol="SPY",
        option_type="CALL",
        expiration=quote.expiration,
        strike=quote.strike,
        side="SELL",
        quantity=1,
        ratio=1,
        position_intent="SELL_TO_OPEN",
        bid=quote.bid,
        ask=quote.ask,
        midpoint=quote.midpoint,
    )
    with pytest.raises(StrategyError, match="Unsafe or malformed"):
        StrategyEngine().validate(StrategyFamily.LONG_CALL, [naked])


@pytest.mark.parametrize(
    ("bias", "profile", "family", "leg_count"),
    [
        (Bias.BULLISH, "AGGRESSIVE", StrategyFamily.LONG_CALL, 1),
        (Bias.BEARISH, "AGGRESSIVE", StrategyFamily.LONG_PUT, 1),
        (Bias.BULLISH, "CONSERVATIVE", StrategyFamily.BULL_CALL_SPREAD, 2),
        (Bias.BEARISH, "CONSERVATIVE", StrategyFamily.BEAR_PUT_SPREAD, 2),
        (Bias.NEUTRAL, "CONSERVATIVE", StrategyFamily.IRON_CONDOR, 4),
    ],
)
def test_supported_strategy_math_is_deterministic(bias, profile, family, leg_count):
    market = AlpacaClient._fixture("SPY")
    request = strategy_request(bias, profile, family)
    engine = StrategyEngine()
    legs = engine.build(market, request)
    strategy, quant = QuantService().evaluate(family, request.thesis, bias, legs, market.underlying_price, market.observed_at, 20)

    assert strategy.strategy_type == family
    assert len(strategy.legs) == leg_count
    assert strategy.max_loss > 0
    assert quant.max_loss == strategy.max_loss
    assert len(quant.scenario_pnl) == 5


def test_hermes_cannot_bypass_quant_validation():
    market = AlpacaClient._fixture("SPY")
    request = strategy_request(Bias.BULLISH, "CONSERVATIVE", StrategyFamily.BULL_CALL_SPREAD)
    legs = StrategyEngine().build(market, request)
    legs[0].quantity = 2
    with pytest.raises(StrategyError, match="one 1:1"):
        QuantService().evaluate(StrategyFamily.BULL_CALL_SPREAD, request.thesis, Bias.BULLISH, legs, market.underlying_price, market.observed_at, 20)


def test_stress_engine_blocks_unsafe_liquidity():
    market = AlpacaClient._fixture("SPY")
    request = strategy_request(Bias.BULLISH, "CONSERVATIVE", StrategyFamily.BULL_CALL_SPREAD)
    legs = StrategyEngine().build(market, request)
    strategy, quant = QuantService().evaluate(StrategyFamily.BULL_CALL_SPREAD, request.thesis, Bias.BULLISH, legs, market.underlying_price, market.observed_at, 20)
    quant.liquidity_passed = False

    assert StressEngine().evaluate(strategy, quant).recommendation == "REJECT"


@pytest.mark.asyncio
async def test_fixture_market_data_cannot_authorize_broker_mutation():
    service = service_for(execution_enabled=True)
    run = await service.run_to_completion(CreateRunRequest(execute=False, simulate_lifecycle=False))
    run.execute_requested = True
    run.decisions = [decision.model_copy(update={"provider": "featherless"}) for decision in run.decisions]
    guard = service._execution_guard(run)

    assert guard.decision == "BLOCK"
    assert "LIVE_EVIDENCE_FOR_MUTATION" in guard.reason_codes


@pytest.mark.asyncio
async def test_fixture_ai_cannot_authorize_broker_mutation():
    service = service_for(execution_enabled=True)
    run = await service.run_to_completion(CreateRunRequest(execute=False, simulate_lifecycle=False))
    run.execute_requested = True
    run.market.source = "alpaca"
    guard = service._execution_guard(run)

    assert guard.decision == "BLOCK"
    assert "LIVE_INFERENCE_FOR_MUTATION" in guard.reason_codes


@pytest.mark.asyncio
async def test_missing_mcp_research_cannot_authorize_broker_mutation():
    service = service_for(execution_enabled=True)
    run = await service.run_to_completion(CreateRunRequest(execute=False, simulate_lifecycle=False))
    run.execute_requested = True
    run.market.source = "alpaca"
    run.decisions = [decision.model_copy(update={"provider": "featherless"}) for decision in run.decisions]

    guard = service._execution_guard(run)

    assert guard.decision == "BLOCK"
    assert "MCP_RESEARCH_FOR_MUTATION" in guard.reason_codes


@pytest.mark.asyncio
async def test_mcp_cannot_execute_trades():
    adapter = AlpacaMcpAdapter(Settings())
    with pytest.raises(IntegrationError, match="not allowlisted"):
        await adapter.call("place_option_order", AgentRole.ATHENA, {"symbol": "SPY"})


def test_mutation_capable_mcp_toolset_is_rejected():
    with pytest.raises(ValueError, match="forbidden"):
        Settings(alpaca_toolsets="stock-data,trading")


def test_mcp_transport_parses_json_and_event_stream_responses():
    json_response = httpx.Response(200, json={"jsonrpc": "2.0", "result": {"ok": True}})
    event_response = httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text='event: message\ndata: {"jsonrpc":"2.0","result":{"ok":true}}\n\n',
    )

    assert AlpacaMcpAdapter._response_body(json_response)["result"]["ok"] is True
    assert AlpacaMcpAdapter._response_body(event_response)["result"]["ok"] is True


def test_live_endpoint_is_rejected_at_configuration_boundary():
    with pytest.raises(ValueError, match="paper endpoint"):
        Settings(alpaca_trading_base_url="https://api.alpaca.markets")
    with pytest.raises(ValueError, match="paper endpoint"):
        Settings(alpaca_trading_base_url="https://paper-api.alpaca.markets.example.com")


def test_alpaca_market_timestamp_drives_freshness():
    observed = AlpacaClient._market_timestamp({"latestTrade": {"p": 100, "t": "2026-09-03T12:34:56Z"}})

    assert observed.isoformat() == "2026-09-03T12:34:56+00:00"


def test_alpaca_evidence_without_timestamp_fails_closed():
    with pytest.raises(IntegrationError, match="timestamp"):
        AlpacaClient._market_timestamp({"latestTrade": {"p": 100}})


@pytest.mark.asyncio
async def test_kill_switch_blocks_execution_path():
    service = service_for()
    service.set_kill_switch(True, "Test halt")
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=False))

    assert run.state == LifecycleState.REJECTED
    assert "KILL_SWITCH" in run.risk.reason_codes


@pytest.mark.asyncio
async def test_expired_risk_approval_blocks_execution():
    service = service_for()
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=False))
    run.risk.expires_at = utc_now() - timedelta(seconds=1)

    guard = service._execution_guard(run)

    assert guard.decision == "BLOCK"
    assert "APPROVAL_VALID" in guard.reason_codes


def test_duplicate_execution_intent_is_blocked():
    store = AuditStore(":memory:")
    run = run_record()
    store.save_run(run)

    assert store.reserve_execution("intent-1", run.id)
    assert not store.reserve_execution("intent-1", run.id)


def test_invalid_state_transition_is_rejected_and_audited():
    service = service_for()
    run = run_record()
    service.store.save_run(run)

    with pytest.raises(RuntimeError, match="Invalid transition"):
        service._transition(run, LifecycleState.SUBMITTED, "TEST", "Invalid jump")
    assert service.store.events(run.id)[0].kind == "STATE_TRANSITION_REJECTED"


@pytest.mark.asyncio
async def test_position_lifecycle_reaches_learned_with_audited_transitions():
    service = service_for()
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=True))
    transitions = [event.payload.get("to") for event in service.store.events(run.id) if event.kind == "STATE_TRANSITION"]

    assert run.state == LifecycleState.LEARNED
    assert run.position and run.position.status == "CLOSED"
    assert run.autopsy and run.memory
    assert run.autopsy.morpheus_verdict in {"PASS", "CAUTION"}
    assert run.autopsy.original_thesis
    assert run.memory.advisory_only is True and run.memory.execution_authority is False
    actors = [event.actor for event in service.store.events(run.id)]
    assert "AUTOPSY_SERVICE" in actors
    assert "LEARNING_SERVICE" in actors
    assert transitions[-9:] == [
        "SUBMITTED", "FILLED", "POSITION_OPEN", "POSITION_MONITORING", "EXIT_SIGNAL",
        "EXIT_EXECUTION", "POSITION_CLOSED", "AUTOPSY", "LEARNED",
    ]


def test_audit_events_and_learning_memory_are_append_only():
    store = AuditStore(":memory:")
    run = run_record()
    store.save_run(run)
    store.append(run.id, "TEST", "SYSTEM", {"ok": True})
    memory = LearningMemory(
        id="00000000-0000-0000-0000-000000000010",
        source_run_id=run.id,
        symbol="SPY",
        lessons=["Test lesson"],
        confidence=0.8,
    )
    store.save_memory(memory)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store._connection.execute("UPDATE audit_events SET actor = 'OTHER'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store._connection.execute("DELETE FROM learning_memories")


def test_learning_memory_has_no_execution_authority():
    memory = LearningMemory(
        id="00000000-0000-0000-0000-000000000010",
        source_run_id="00000000-0000-0000-0000-000000000001",
        symbol="SPY",
        lessons=["Stay cautious"],
        confidence=0.8,
    )
    assert memory.advisory_only is True
    assert memory.execution_authority is False
    with pytest.raises(ValidationError):
        LearningMemory(**{**memory.model_dump(), "execution_authority": True})


def test_malformed_llm_output_fails_closed():
    client = FeatherlessClient(Settings())
    with pytest.raises(IntegrationError, match="Malformed ATHENA"):
        client.parse_for_test(AgentRole.ATHENA, {"confidence": 0.9, "bias": "BULLISH"})


@pytest.mark.asyncio
async def test_mcp_calls_are_visible_in_replay():
    service = service_for()
    run = await service.run_to_completion(CreateRunRequest(simulate_lifecycle=False))
    replay = service.store.events(run.id)

    assert len(run.mcp_calls) == 3
    assert all(call.success for call in run.mcp_calls)
    assert sum(event.kind == "MCP_TOOL_CALL" for event in replay) == 3


def test_sqlite_remains_default_persistence():
    store = build_store("", ":memory:")
    assert store.backend_name == "sqlite"


def test_legacy_run_snapshots_do_not_break_current_run_listing():
    store = AuditStore(":memory:")
    store._connection.execute(
        "INSERT INTO workflow_runs(id, symbol, state, status, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("legacy", "SPY", "DETECTED", "DONE", '{"id":"legacy"}', utc_now().isoformat(), utc_now().isoformat()),
    )
    current = run_record()
    store.save_run(current)

    assert store.get_run("legacy") is None
    assert [run.id for run in store.list_runs()] == [current.id]
