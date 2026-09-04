import asyncio
import base64
import hashlib
import hmac
import json
import sqlite3
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.domain import (
    AgentRole,
    AthenaDecision,
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


def auth_token(role: str, secret: str = "unit-test-secret", sub: str = "tester") -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub, "role": role}).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


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
    with pytest.raises(ValueError, match="forbidden"):
        Settings(alpaca_toolsets="stock-data,account")


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
    with pytest.raises(ValueError, match="data URL"):
        Settings(alpaca_data_base_url="https://data.alpaca.markets.example.com")


def test_sensitive_provider_hosts_are_allowlisted():
    with pytest.raises(ValueError, match="Featherless"):
        Settings(featherless_base_url="http://api.featherless.ai/v1")
    with pytest.raises(ValueError, match="Featherless"):
        Settings(featherless_base_url="https://evil.example/v1")
    with pytest.raises(ValueError, match="MCP"):
        Settings(mcp_server_url="http://public.example/mcp")


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


def test_durable_kill_switch_survives_service_restart(tmp_path):
    db_path = str(tmp_path / "oracle-x.db")
    service = service_for(db_path)
    service.set_kill_switch(True, "Persist halt", actor="operator-test")

    restarted = service_for(db_path)

    assert restarted.kill_switch is True
    assert restarted.system_state.status == "HALTED"
    assert restarted.system_state.changed_by == "operator-test"


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


@pytest.mark.asyncio
async def test_duplicate_economic_intent_is_blocked_before_second_order():
    service = service_for(execution_enabled=True)
    run = await service.run_to_completion(CreateRunRequest(execute=False, simulate_lifecycle=False))
    run.mode = "connected"
    run.execute_requested = True
    run.market.source = "alpaca"
    run.decisions = [decision.model_copy(update={"provider": "featherless"}) for decision in run.decisions]
    fingerprint = service._execution_fingerprint(run)
    service.store.reserve_execution_intent("existing-intent", run.id, fingerprint)

    assert service.store.has_active_execution_conflict(fingerprint)


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
async def test_featherless_429_retry_after_is_respected(monkeypatch):
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "0.25"}, json={"error": "rate limited"}, request=httpx.Request("POST", "https://api.featherless.ai/v1/chat/completions")),
            httpx.Response(
                200,
                request=httpx.Request("POST", "https://api.featherless.ai/v1/chat/completions"),
                json={
                    "id": "trace-1",
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "confidence": 0.8,
                                        "evidence_refs": ["market"],
                                        "thesis": "SPY has a bounded paper-trading test opportunity.",
                                        "bias": "BULLISH",
                                    }
                                )
                            }
                        }
                    ],
                },
            ),
        ]
    )
    sleeps = []

    class FeatherlessHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return next(responses)

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FeatherlessHttpClient())
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    client = FeatherlessClient(Settings(featherless_api_key="test", featherless_max_retries=1))

    decision = await client.athena({"symbol": "SPY"})

    assert decision.provider == "featherless"
    assert sleeps == [0.25]


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


def test_mleg_debit_and_credit_limit_price_signs_are_correct():
    market = AlpacaClient._fixture("SPY")
    engine = StrategyEngine()
    bull_request = strategy_request(Bias.BULLISH, "CONSERVATIVE", StrategyFamily.BULL_CALL_SPREAD)
    bull_legs = engine.build(market, bull_request)
    bull_strategy, _ = QuantService().evaluate(StrategyFamily.BULL_CALL_SPREAD, bull_request.thesis, Bias.BULLISH, bull_legs, market.underlying_price, market.observed_at, 20)
    condor_request = strategy_request(Bias.NEUTRAL, "CONSERVATIVE", StrategyFamily.IRON_CONDOR)
    condor_legs = engine.build(market, condor_request)
    condor_strategy, _ = QuantService().evaluate(StrategyFamily.IRON_CONDOR, condor_request.thesis, Bias.NEUTRAL, condor_legs, market.underlying_price, market.observed_at, 20)
    client = AlpacaClient(Settings())

    debit_payload = client.order_payload(bull_strategy, "debit")
    credit_payload = client.order_payload(condor_strategy, "credit")

    assert float(debit_payload["limit_price"]) > 0
    assert float(credit_payload["limit_price"]) < 0
    assert debit_payload["order_class"] == credit_payload["order_class"] == "mleg"


@pytest.mark.asyncio
async def test_option_chain_uses_supported_snapshot_parameters():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "/v2/options/contracts" in str(request.url):
            contracts = []
            for strike in [95, 100, 105, 110]:
                for option_type in ["call", "put"]:
                    contracts.append(
                        {
                            "symbol": f"SPY260101{option_type[0].upper()}{strike}",
                            "expiration_date": "2026-01-01",
                            "strike_price": str(strike),
                            "type": option_type,
                            "status": "active",
                        }
                    )
            return httpx.Response(200, json={"option_contracts": contracts})
        snapshots = {
            f"SPY260101{kind}{strike}": {
                "latestQuote": {"bp": 1.0, "ap": 1.2, "t": "2026-09-04T12:00:00Z"},
                "greeks": {"delta": 0.3},
                "impliedVolatility": 0.2,
            }
            for strike in [95, 100, 105, 110]
            for kind in ["C", "P"]
        }
        return httpx.Response(200, json={"snapshots": snapshots})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        quotes, _ = await AlpacaClient(Settings())._option_chain(client, "SPY", 100)

    snapshot_request = [request for request in requests if "/v1beta1/options/snapshots/" in str(request.url)][0]
    assert "symbols=" not in str(snapshot_request.url)
    assert len(quotes) >= 4


@pytest.mark.asyncio
async def test_unknown_broker_submission_queries_by_client_order_id(monkeypatch):
    market = AlpacaClient._fixture("SPY")
    request = strategy_request(Bias.BULLISH, "CONSERVATIVE", StrategyFamily.BULL_CALL_SPREAD)
    legs = StrategyEngine().build(market, request)
    strategy, _ = QuantService().evaluate(StrategyFamily.BULL_CALL_SPREAD, request.thesis, Bias.BULLISH, legs, market.underlying_price, market.observed_at, 20)
    client = AlpacaClient(Settings(execution_enabled=True, alpaca_api_key="key", alpaca_api_secret="secret"))
    looked_up = {"called": False}

    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            raise httpx.TimeoutException("submission timed out")

    async def lookup(client_order_id):
        looked_up["called"] = client_order_id == "idem-1"
        return None

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: TimeoutClient())
    monkeypatch.setattr(client, "lookup_order", lookup)

    order = await client.submit_strategy(strategy, "idem-1")

    assert looked_up["called"] is True
    assert order["reconciliation_status"] == "UNKNOWN"
    assert order["status"] == "unknown"


def test_normalized_runtime_persistence_records_are_written():
    store = AuditStore(":memory:")
    run = run_record()
    store.save_run(run)
    decision = FeatherlessClient(Settings())._fixture(AgentRole.ATHENA, {"symbol": "SPY"}, AthenaDecision)
    store.save_agent_decision(run.id, decision)
    store.save_broker_order(
        run.id,
        {
            "client_order_id": "cid",
            "order_id": "oid",
            "status": "submitted",
            "request_payload": {"ok": True},
            "raw_response": {"id": "oid"},
        },
    )
    assert store._connection.execute("SELECT count(*) FROM inference_traces").fetchone()[0] == 1
    assert store._connection.execute("SELECT count(*) FROM broker_orders_runtime").fetchone()[0] == 1


def test_api_requires_authentication_and_operator_for_mutations(monkeypatch):
    from app import main
    from app.config import get_settings

    settings = Settings(jwt_secret="unit-test-secret")
    main.app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(main.app)

    assert client.get("/api/health").status_code == 401
    assert client.post("/api/system/kill-switch", params={"active": True}).status_code == 401
    read_headers = {"Authorization": f"Bearer {auth_token('read')}"}
    operator_headers = {"Authorization": f"Bearer {auth_token('operator')}"}
    assert client.get("/api/health", headers=read_headers).status_code == 200
    assert client.post("/api/system/kill-switch", params={"active": True, "reason": "test"}, headers=read_headers).status_code == 403
    assert client.post("/api/system/kill-switch", params={"active": True, "reason": "test"}, headers=operator_headers).status_code == 200
    main.app.dependency_overrides.clear()


def test_supabase_security_migration_documents_rls_expectations():
    sql = open("supabase/migrations/004_connected_security_remediation.sql", encoding="utf-8").read()

    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon" in sql
    assert "ALTER TABLE execution_intents ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE oracle_events ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE broker_orders_runtime ENABLE ROW LEVEL SECURITY" in sql
    assert "auth.role() = 'service_role'" in sql
